from flask import Blueprint, request

from Delivery_app_BK.services.commands.integration_shopify.webhooks import verify_shopify_webhook, reserve_webhook_event

from Delivery_app_BK.services.commands.integration_shopify.webhooks import(
    webhook_event_completed,
    webhook_event_processing,
    webhook_event_failed,
    kill_event
)
from Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound import (
    create_internal_order as create_shopify_internal_order )

from pprint import pprint


shopify_webhook_bp = Blueprint("shopify_webhook_bp", __name__)


@shopify_webhook_bp.route("/orders", methods=["POST"])
def shopify_orders_webhook():
    raw_body = request.get_data()
    headers = request.headers

    # verify the hook received
    verify_shopify_webhook(raw_body, headers)

    webhook_id = headers.get("X-Shopify-Webhook-Id")
    shop_domain = headers.get("X-Shopify-Shop-Domain")
    topic = headers.get("X-Shopify-Topic")
    
    event, created = reserve_webhook_event(
        webhook_id=webhook_id,
        shop_domain=shop_domain,
        topic=topic
    )

    if not created:
        if event.status == "completed":
            return "", 200
        if event.retry_counter > 3:
            kill_event( event )
            return "", 200
        if event.status in ("processing", "failed"):
            webhook_event_processing(event)
            return "", 500  # force retry


    payload = request.get_json(silent=True) or {}
    
    try:

        create_shopify_internal_order(
            shop = shop_domain,
            payload = payload
        )
        
        webhook_event_completed(event)

        return "", 200
    except Exception as e:
        print('ERROR:', str(e))
        webhook_event_failed(event)
        return "", 500
   

 

@shopify_webhook_bp.route("/orders/test", methods=["POST"])
def shop_test():
    payload = request.get_json(silent=True) or {}
    create_shopify_internal_order(
        shop = "teststoredeliveryapp.myshopify.com",
        payload = payload
    )
    return "",200