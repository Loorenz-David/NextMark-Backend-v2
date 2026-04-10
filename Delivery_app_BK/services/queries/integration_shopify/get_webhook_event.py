from Delivery_app_BK.models import db, ShopifyWebhookEvents

def get_webhook_event(webhook_id):
    
    webhook = db.session.query(ShopifyWebhookEvents).filter(
        ShopifyWebhookEvents.webhook_id == webhook_id
    ).first()

    return webhook