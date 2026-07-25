"""Inbound sync: a customer edited in Shopify updates the linked local Costumer.

Scope: name, email, primary phone and the default address. Shopify customer
addresses carry no coordinates, so the address is geocoded (which yields the
lat/lng our routing requires) before it is applied; when an active order's address
changes, its route plan is marked stale so the stop is re-optimized.

Loop safety (two independent guards):
  1. Content diff — if the incoming Shopify data already matches what we hold, we
     do nothing. This absorbs the echo of our own outbound push (which made the two
     sides equal), so the common case never writes.
  2. No outbound re-trigger — the cascade updates orders directly and emits only an
     EDITED event (which has no Shopify handler). It never emits CLIENT_FORM_SUBMITTED,
     so an inbound apply can never bounce back out to Shopify.
"""

from __future__ import annotations

import logging
from typing import Any

import phonenumbers

from Delivery_app_BK.geocoding.orchestrator import geocode_address
from Delivery_app_BK.models import Costumer, Order, OrderState, db
from Delivery_app_BK.services.commands.costumer.default_rows import (
    upsert_default_address,
    upsert_default_phone,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_states import OrderState as OrderStateName
from Delivery_app_BK.services.domain.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.queries.integration_shopify import get_integration_by_shop
from Delivery_app_BK.services.requests.costumer.common import normalize_email


logger = logging.getLogger(__name__)

SHOPIFY_EXTERNAL_SOURCE = "shopify"
TERMINAL_STATE_NAMES = {
    OrderStateName.COMPLETED.value,
    OrderStateName.FAIL.value,
    OrderStateName.CANCELLED.value,
}


def apply_shopify_customer_update(shop: str, payload: dict) -> None:
    external_id = _external_customer_id(payload)
    if not external_id:
        logger.warning("[shopify-customer-inbound] missing customer id | shop=%s", shop)
        return

    integration = get_integration_by_shop(shop)
    if integration is None:
        logger.error("[shopify-customer-inbound] integration not found | shop=%s", shop)
        return
    team_id = integration.team_id

    costumer = (
        db.session.query(Costumer)
        .filter(
            Costumer.team_id == team_id,
            Costumer.external_source == SHOPIFY_EXTERNAL_SOURCE,
            Costumer.external_costumer_id == external_id,
        )
        .first()
    )
    if costumer is None:
        logger.info(
            "[shopify-customer-inbound] no linked costumer | shop=%s external_id=%s",
            shop,
            external_id,
        )
        return

    incoming = _map_customer_payload(payload)
    changes = _diff_costumer(costumer, incoming)

    # Address needs geocoding, so it is resolved separately and only when the raw
    # Shopify address differs from what we already hold (avoids needless API calls).
    changed_address = _resolve_changed_address(costumer, payload)
    if changed_address is not None:
        incoming["address"] = changed_address
        changes.add("address")

    if not changes:
        # Loop-breaker #1: already in sync (typically our own outbound echo).
        logger.info(
            "[shopify-customer-inbound] no-op, already in sync | costumer_id=%s external_id=%s",
            costumer.id,
            external_id,
        )
        return

    _apply_costumer_changes(costumer, incoming, changes, team_id)
    updated_orders = _cascade_to_active_orders(costumer, incoming, changes, team_id)
    db.session.add(costumer)
    db.session.commit()

    logger.info(
        "[shopify-customer-inbound] applied | costumer_id=%s changed=%s cascaded_orders=%s",
        costumer.id,
        sorted(changes),
        [order.id for order in updated_orders],
    )

    # Loop-breaker #2: EDITED only — no CLIENT_FORM_SUBMITTED, so no push back out.
    if updated_orders:
        ctx = ServiceContext(identity={"team_id": team_id, "active_team_id": team_id})
        emit_order_events(
            ctx,
            [
                build_order_edited_event(order, changed_sections=["shopify_customer_sync"])
                for order in updated_orders
            ],
        )


def _external_customer_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("id")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _map_customer_payload(payload: dict) -> dict[str, Any]:
    return {
        "first_name": _clean_str(payload.get("first_name")),
        "last_name": _clean_str(payload.get("last_name")),
        "email": normalize_email(payload.get("email")),
        "phone": _phone_parts_from_e164(payload.get("phone")),
    }


def _diff_costumer(costumer: Costumer, incoming: dict[str, Any]) -> set[str]:
    """Fields with a non-empty incoming value that differs from what we store."""
    changes: set[str] = set()
    if incoming["first_name"] and incoming["first_name"] != costumer.first_name:
        changes.add("first_name")
    if incoming["last_name"] and incoming["last_name"] != costumer.last_name:
        changes.add("last_name")
    if incoming["email"] and incoming["email"] != normalize_email(costumer.email):
        changes.add("email")
    if incoming["phone"] and incoming["phone"] != _default_primary_phone(costumer):
        changes.add("phone")
    return changes


def _apply_costumer_changes(
    costumer: Costumer,
    incoming: dict[str, Any],
    changes: set[str],
    team_id: int,
) -> None:
    if "first_name" in changes:
        costumer.first_name = incoming["first_name"]
    if "last_name" in changes:
        costumer.last_name = incoming["last_name"]
    if "email" in changes:
        costumer.email = incoming["email"]
    if "phone" in changes:
        upsert_default_phone(costumer, incoming["phone"], team_id, slot="primary")
    if "address" in changes:
        upsert_default_address(costumer, incoming["address"], team_id)


def _cascade_to_active_orders(
    costumer: Costumer,
    incoming: dict[str, Any],
    changes: set[str],
    team_id: int,
) -> list[Order]:
    orders = (
        db.session.query(Order)
        .join(OrderState, Order.order_state_id == OrderState.id)
        .filter(
            Order.team_id == team_id,
            Order.costumer_id == costumer.id,
            OrderState.name.notin_(TERMINAL_STATE_NAMES),
        )
        .all()
    )

    for order in orders:
        if "first_name" in changes:
            order.client_first_name = incoming["first_name"]
        if "last_name" in changes:
            order.client_last_name = incoming["last_name"]
        if "email" in changes:
            order.client_email = incoming["email"]
        if "phone" in changes:
            order.client_primary_phone = incoming["phone"]
        if "address" in changes:
            order.client_address = incoming["address"]
            delivery_plan = getattr(order, "delivery_plan", None)
            if delivery_plan is not None:
                # The stop moved — mark the plan stale so it is re-optimized.
                touch_route_freshness(delivery_plan)
        db.session.add(order)

    return orders


def _resolve_changed_address(costumer: Costumer, payload: dict) -> dict[str, Any] | None:
    """Return a geocoded address dict when the Shopify address genuinely changed.

    Cheap signature pre-filter avoids geocoding on the common echo case; the final
    equality check against the stored address avoids a needless write/cascade when
    geocoding lands on the same result we already hold.
    """
    shopify_address = _shopify_address_from_payload(payload)
    if not shopify_address:
        return None

    current = _default_address(costumer)
    if _address_signature_shopify(shopify_address) == _address_signature_stored(current):
        return None

    resolved = _geocode_shopify_address(shopify_address)
    if resolved is None or resolved == current:
        return None
    return resolved


def _geocode_shopify_address(shopify_address: dict) -> dict[str, Any] | None:
    query = _build_address_query(shopify_address)
    if not query:
        return None
    try:
        result = geocode_address(query, country_hint=_country_hint(shopify_address))
    except Exception:
        # Never fail the whole customer sync (name/email/phone) on a geocode error
        # or missing geocoding credentials — just skip the address this round.
        logger.exception("[shopify-customer-inbound] geocode failed; skipping address")
        return None
    if result is None:
        logger.warning("[shopify-customer-inbound] geocode no match | query=%r", query)
        return None
    return result.to_address_dict()


def _shopify_address_from_payload(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None
    default_address = payload.get("default_address")
    if isinstance(default_address, dict) and default_address:
        return default_address
    for entry in payload.get("addresses") or []:
        if isinstance(entry, dict) and entry:
            return entry
    return None


def _build_address_query(shopify_address: dict) -> str | None:
    parts = [
        shopify_address.get("address1"),
        shopify_address.get("address2"),
        shopify_address.get("zip"),
        shopify_address.get("city"),
        shopify_address.get("province"),
        shopify_address.get("country"),
    ]
    query = ", ".join(str(part).strip() for part in parts if isinstance(part, str) and part.strip())
    return query or None


def _country_hint(shopify_address: dict) -> str | None:
    code = shopify_address.get("country_code")
    if isinstance(code, str) and len(code.strip()) == 2 and code.strip().isalpha():
        return code.strip().upper()
    return None


def _default_address(costumer: Costumer) -> dict[str, Any] | None:
    default_id = costumer.default_address_id
    if default_id is None:
        return None
    for row in costumer.addresses or []:
        if row.id == default_id and isinstance(row.address, dict):
            return row.address
    return None


def _address_signature_shopify(shopify_address: dict) -> tuple[str, str, str, str]:
    street = f"{shopify_address.get('address1') or ''} {shopify_address.get('address2') or ''}"
    country = shopify_address.get("country_code") or shopify_address.get("country")
    return (
        _norm(street),
        _norm(shopify_address.get("city")),
        _norm(shopify_address.get("zip")),
        _norm(country),
    )


def _address_signature_stored(address: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if not isinstance(address, dict):
        return ("", "", "", "")
    return (
        _norm(address.get("street_address")),
        _norm(address.get("city")),
        _norm(address.get("postal_code")),
        _norm(address.get("country")),
    )


def _norm(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _default_primary_phone(costumer: Costumer) -> dict[str, str] | None:
    default_id = costumer.default_primary_phone_id
    if default_id is None:
        return None
    for row in costumer.phones or []:
        if row.id == default_id and isinstance(row.phone, dict):
            return row.phone
    return None


def _phone_parts_from_e164(value: Any) -> dict[str, str] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = phonenumbers.parse(value.strip(), None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return {
        "prefix": f"+{parsed.country_code}",
        "number": str(parsed.national_number),
    }


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
