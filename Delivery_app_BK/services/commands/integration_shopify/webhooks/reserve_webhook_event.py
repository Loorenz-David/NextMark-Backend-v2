# services/commands/integration_shopify/reserve_webhook_event.py
from sqlalchemy.exc import IntegrityError
from Delivery_app_BK.models import db, ShopifyWebhookEvents

def reserve_webhook_event(webhook_id, shop_domain, topic):
    try:
        event = ShopifyWebhookEvents(
            webhook_id=webhook_id,
            shop_domain=shop_domain,
            topic=topic,
            retry_counter = 0,
            status="processing"
        )
        db.session.add(event)
        db.session.commit()
        return event, True
    except IntegrityError:
        db.session.rollback()
        event = ShopifyWebhookEvents.query.filter_by(
            webhook_id=webhook_id
        ).one()
        return event, False