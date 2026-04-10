import requests
from Delivery_app_BK.errors import ValidationFailed

def create_shopify_webhook(shop, access_token, topic, address):
    url = f"https://{shop}/admin/api/2024-01/webhooks.json"

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    payload = {
        "webhook": {
            "topic": topic,
            "address": address,
            "format": "json",
        }
    }

    response = requests.post(url, json=payload, headers=headers, timeout=10)
  

    if response.status_code in (200, 201):
        return response.json()


    try:
        body = response.json()
    except ValueError:
        body = {}

    if (
        response.status_code == 422
        and body.get("errors", {})
        .get("address", [])[0]
        .startswith("for this topic has already been taken")
    ):
        return {
            "status": "already_exists",
            "topic": topic,
            "address": address,
        }


    raise ValidationFailed(
        f"Failed to create Shopify webhook "
        f"({response.status_code}): {body or response.text}"
    )

