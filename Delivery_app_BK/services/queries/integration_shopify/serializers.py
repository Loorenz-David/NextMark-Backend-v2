from Delivery_app_BK.models import ShopifyIntegration


def serialize_shopify_integration(instance: ShopifyIntegration) -> dict:
    connected_at = instance.connected_at
    return {
        "id": str(instance.id),
        "shop": instance.shop,
        "scopes": instance.scopes,
        "connected_at": connected_at.isoformat() if connected_at else None,
    }
