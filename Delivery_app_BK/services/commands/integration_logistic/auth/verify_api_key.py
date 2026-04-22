import hmac
import os

from Delivery_app_BK.errors import ValidationFailed


LOGISTIC_API_KEY = os.getenv("LOGISTIC_API_KEY")


def verify_api_key(headers: dict) -> None:
    received_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    if not LOGISTIC_API_KEY or not received_key:
        raise ValidationFailed("Unauthorized")
    if not hmac.compare_digest(LOGISTIC_API_KEY, received_key):
        raise ValidationFailed("Unauthorized")
