from flask import Blueprint, current_app, request

from Delivery_app_BK.services.commands.integration_shopify.webhooks import (
    verify_shopify_webhook,
    reserve_webhook_event,
    kill_event,
)
from Delivery_app_BK.services.infra.jobs import enqueue_job, DEFAULT_RETRY_POLICY
from Delivery_app_BK.services.infra.jobs.tasks.shopify import process_shopify_order_webhook_job

shopify_webhook_bp = Blueprint("shopify_webhook_bp", __name__)


@shopify_webhook_bp.route("/orders", methods=["POST"])
def shopify_orders_webhook():
    raw_body = request.get_data()
    headers = request.headers

    webhook_id = headers.get("X-Shopify-Webhook-Id")
    shop_domain = headers.get("X-Shopify-Shop-Domain")
    topic = headers.get("X-Shopify-Topic")
    current_app.logger.info(
        "Shopify webhook received | webhook_id=%s shop=%s topic=%s body_bytes=%s",
        webhook_id,
        shop_domain,
        topic,
        len(raw_body or b""),
    )

    # verify the hook received
    try:
        verify_shopify_webhook(raw_body, headers)
        current_app.logger.info(
            "Shopify webhook signature verified | webhook_id=%s",
            webhook_id,
        )
    except Exception:
        current_app.logger.exception(
            "Shopify webhook signature verification failed | webhook_id=%s shop=%s topic=%s",
            webhook_id,
            shop_domain,
            topic,
        )
        raise

    event, created = reserve_webhook_event(
        webhook_id=webhook_id,
        shop_domain=shop_domain,
        topic=topic
    )
    current_app.logger.info(
        "Shopify webhook event reserved | webhook_id=%s event_id=%s created=%s status=%s retries=%s",
        webhook_id,
        getattr(event, "id", None),
        created,
        getattr(event, "status", None),
        getattr(event, "retry_counter", None),
    )

    if not created:
        if event.status == "completed":
            current_app.logger.info(
                "Shopify webhook ignored as already completed | webhook_id=%s event_id=%s",
                webhook_id,
                getattr(event, "id", None),
            )
            return "", 200
        if event.retry_counter > 3:
            kill_event(event)
            current_app.logger.warning(
                "Shopify webhook dead-lettered after retries | webhook_id=%s event_id=%s retries=%s",
                webhook_id,
                getattr(event, "id", None),
                getattr(event, "retry_counter", None),
            )
            return "", 200
        # duplicate delivery while still processing — re-enqueue and ack
        current_app.logger.warning(
            "Shopify webhook duplicate delivery re-enqueued | webhook_id=%s event_id=%s status=%s",
            webhook_id,
            getattr(event, "id", None),
            getattr(event, "status", None),
        )

    payload = request.get_json(silent=True) or {}
    current_app.logger.info(
        "Shopify webhook enqueuing job | webhook_id=%s event_id=%s order_id=%s",
        webhook_id,
        getattr(event, "id", None),
        payload.get("id") if isinstance(payload, dict) else None,
    )

    enqueue_job(
        queue_key="default",
        fn=process_shopify_order_webhook_job,
        args=(event.id, shop_domain, payload),
        retry_policy=DEFAULT_RETRY_POLICY,
        description=f"shopify-order-webhook:{webhook_id}",
    )

    return "", 200
   

 

@shopify_webhook_bp.route("/orders/test", methods=["POST"])
def shop_test():
    from Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound import (
        create_internal_order as create_shopify_internal_order,
    )
    payload = request.get_json(silent=True) or {}
    create_shopify_internal_order(
        shop="teststoredeliveryapp.myshopify.com",
        payload=payload,
    )
    return "", 200