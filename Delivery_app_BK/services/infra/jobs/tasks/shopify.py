from __future__ import annotations

import logging

from Delivery_app_BK.services.infra.jobs import with_app_context

logger = logging.getLogger(__name__)


@with_app_context
def process_shopify_order_webhook_job(event_id: int, shop: str, payload: dict) -> None:
    from Delivery_app_BK.models import ShopifyWebhookEvents
    from Delivery_app_BK.services.commands.integration_shopify.webhooks import (
        webhook_event_completed,
        webhook_event_failed,
    )
    from Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound import (
        create_internal_order as create_shopify_internal_order,
    )

    event = ShopifyWebhookEvents.query.get(event_id)
    if event is None:
        logger.error("process_shopify_order_webhook_job: event_id=%s not found", event_id)
        return

    try:
        create_shopify_internal_order(shop=shop, payload=payload)
        webhook_event_completed(event)
        logger.info(
            "Shopify order webhook processed successfully | event_id=%s shop=%s order_id=%s",
            event_id,
            shop,
            payload.get("id") if isinstance(payload, dict) else None,
        )
    except Exception:
        webhook_event_failed(event)
        logger.exception(
            "Shopify order webhook processing failed | event_id=%s shop=%s order_id=%s",
            event_id,
            shop,
            payload.get("id") if isinstance(payload, dict) else None,
        )
        raise
