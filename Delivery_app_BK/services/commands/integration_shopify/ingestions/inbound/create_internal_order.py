import logging

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Costumer, ShopifyWebhookEvents, db
from Delivery_app_BK.services.queries.integration_shopify import get_integration_by_shop
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.order import create_order
from Delivery_app_BK.services.commands.costumer.create_costumer import create_costumer
from Delivery_app_BK.services.domain.order.shopify_intent_sku import (
        FLAG_SKUS_TO_EXCLUDE,
        INTENT_SKU_TO_PLAN_OBJECTIVE,
        resolve_intent_from_shopify_line_items,
)
from .line_item_enrichment import (
        ShopifyMetafieldResolver,
        ShopifyLineItemMediaResolver,
        apply_shopify_line_item_media,
        enrich_mapped_item_from_shopify_line_item,
)
from ..mappers import item_mapper, order_mapper


logger = logging.getLogger(__name__)

def create_internal_order(
        shop:str,
        payload: dict,
):
        external_order_id = payload.get("id") if isinstance(payload, dict) else None
        line_items = payload.get("line_items") or [] if isinstance(payload, dict) else []
        logger.info(
                "Shopify inbound create_internal_order start | shop=%s external_order_id=%s line_items=%s",
                shop,
                external_order_id,
                len(line_items),
        )

        shopify_shop = get_integration_by_shop(shop)

        if not shopify_shop:
                logger.error(
                        "Shopify inbound missing integration | shop=%s external_order_id=%s",
                        shop,
                        external_order_id,
                )
                raise NotFound(f"Shop integration not found with name: {shop}")
       
        order =  order_mapper(payload)
        customer_payload = payload.get("customer") if isinstance(payload, dict) else None

        metafield_resolver = ShopifyMetafieldResolver(shopify_shop)
        item_pairs = [
                (
                        line_item,
                        enrich_mapped_item_from_shopify_line_item(
                        mapped_item=item_mapper(line_item),
                        line_item=line_item,
                        integration=shopify_shop,
                        resolver=metafield_resolver,
                        ),
                )
                for line_item in line_items
        ]
        items = [item for _line_item, item in item_pairs]
        plan_objective, should_suppress = resolve_intent_from_shopify_line_items(line_items)
        logger.info(
                "Shopify inbound intent resolved | shop=%s external_order_id=%s plan_objective=%s suppress=%s mapped_items=%s",
                shop,
                external_order_id,
                plan_objective,
                should_suppress,
                len(items),
        )

        if should_suppress:
                logger.warning(
                        "Shopify inbound order suppressed by SKU intent rules | shop=%s external_order_id=%s",
                        shop,
                        external_order_id,
                )
                return

        reserved_skus = set(INTENT_SKU_TO_PLAN_OBJECTIVE) | set(FLAG_SKUS_TO_EXCLUDE)
        before_filter_count = len(items)
        item_pairs = [
                (line_item, item)
                for line_item, item in item_pairs
                if str(item.get("article_number")).strip().upper() not in reserved_skus
        ]
        items = [item for _line_item, item in item_pairs]
        logger.info(
                "Shopify inbound item filtering complete | shop=%s external_order_id=%s before=%s after=%s removed_reserved=%s",
                shop,
                external_order_id,
                before_filter_count,
                len(items),
                before_filter_count - len(items),
        )

        media_resolver = ShopifyLineItemMediaResolver(
                shopify_shop,
                [line_item for line_item, _item in item_pairs],
        )
        items = [
                apply_shopify_line_item_media(
                        mapped_item=item,
                        line_item=line_item,
                        resolver=media_resolver,
                )
                for line_item, item in item_pairs
        ]

        order['items'] = items
        order["order_plan_objective"] = plan_objective
        identity = {'team_id': shopify_shop.team_id}

        if isinstance(customer_payload, dict):
                costumer_id = _resolve_or_create_shopify_costumer_id(
                        team_id=shopify_shop.team_id,
                        shopify_customer=customer_payload,
                        order_payload=order,
                )
                if costumer_id is not None:
                        order["costumer"] = {"costumer_id": costumer_id}
                        logger.info(
                                "Shopify inbound customer resolved | shop=%s external_order_id=%s costumer_id=%s",
                                shop,
                                external_order_id,
                                costumer_id,
                        )
                else:
                        logger.warning(
                                "Shopify inbound customer resolution returned no id | shop=%s external_order_id=%s",
                                shop,
                                external_order_id,
                        )

        ctx = ServiceContext(
                incoming_data= { "fields": order },
                identity=identity,
        )

        result = create_order( ctx )
        created_count = len((result or {}).get("created") or [])
        logger.info(
                "Shopify inbound create_order completed | shop=%s external_order_id=%s created_count=%s",
                shop,
                external_order_id,
                created_count,
        )


def _resolve_or_create_shopify_costumer_id(
        *,
        team_id: int,
        shopify_customer: dict,
        order_payload: dict,
) -> int | None:
        external_costumer_id = shopify_customer.get("id")
        normalized_external_costumer_id = (
                str(external_costumer_id).strip()
                if external_costumer_id is not None
                else None
        )
        if normalized_external_costumer_id:
                existing = (
                        db.session.query(Costumer)
                        .filter(
                                Costumer.team_id == team_id,
                                Costumer.external_source == "shopify",
                                Costumer.external_costumer_id == normalized_external_costumer_id,
                        )
                        .first()
                )
                if existing is not None:
                        return existing.id

        customer_fields = _build_shopify_costumer_fields(
                shopify_customer=shopify_customer,
                order_payload=order_payload,
        )
        ctx = ServiceContext(
                incoming_data={"fields": customer_fields},
                identity={"team_id": team_id, "active_team_id": team_id},
        )
        result = create_costumer(ctx)
        created = (result.get("created") or [{}])[0].get("costumer") or {}
        return created.get("id")


def _build_shopify_costumer_fields(
        *,
        shopify_customer: dict,
        order_payload: dict,
) -> dict:
        first_name = (shopify_customer.get("first_name") or order_payload.get("client_first_name") or "Shopify").strip()
        last_name = (shopify_customer.get("last_name") or order_payload.get("client_last_name") or "Customer").strip()

        fields = {
                "first_name": first_name,
                "last_name": last_name,
                "email": shopify_customer.get("email") or order_payload.get("client_email"),
                "external_source": "shopify",
                "external_costumer_id": str(shopify_customer.get("id")) if shopify_customer.get("id") is not None else None,
        }

        phone = order_payload.get("client_primary_phone")
        if isinstance(phone, dict):
                fields["phones"] = [
                        {
                                "phone": phone,
                                "is_default_primary": True,
                        }
                ]

        address = order_payload.get("client_address")
        if isinstance(address, dict):
                fields["addresses"] = [
                        {
                                "address": address,
                                "is_default": True,
                        }
                ]

        return fields
        
