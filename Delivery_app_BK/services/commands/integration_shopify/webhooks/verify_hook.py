import hmac
import os
import hashlib
import base64

from Delivery_app_BK.errors import ValidationFailed



SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")



def verify_shopify_webhook(raw_body: bytes, headers: dict) -> None:
    received_hmac = headers.get("X-Shopify-Hmac-Sha256")
    if not received_hmac:
        raise ValidationFailed("Missing webhook HMAC")
    if not SHOPIFY_CLIENT_SECRET:
        raise RuntimeError("SHOPIFY_CLIENT_SECRE not configured ")

    digest = hmac.new(
        SHOPIFY_CLIENT_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).digest()

    calculated_hmac = base64.b64encode(digest).decode()

    if not hmac.compare_digest(calculated_hmac, received_hmac):
        raise ValidationFailed("Invalid webhook signature")

   