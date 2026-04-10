# services/commands/integration_shopify/update_webhook_status.py
from Delivery_app_BK.models import db, ShopifyWebhookEvents


def webhook_event_completed(event:ShopifyWebhookEvents):    
    event.status = 'completed'
    db.session.commit()
def webhook_event_processing(event:ShopifyWebhookEvents):    
    event.status = 'processing'
    db.session.commit()

def webhook_event_failed(event:ShopifyWebhookEvents):    
    event.status = 'failed'
    event.retry_counter = 1 + event.retry_counter
    db.session.commit()

def kill_event(event:ShopifyWebhookEvents):
    event.status = "dead"
    event.dead_letter_attempt = f"Failed after {event.retry_counter} attempts"
    db.session.commit()