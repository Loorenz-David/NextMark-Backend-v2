from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ShopifyIntegration
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance

from .serializers import serialize_shopify_integration


def get_shopify_details(ctx: ServiceContext, integration_id: str) -> dict:
    if not integration_id.isdigit():
        raise ValidationFailed("Shopify integration id must be numeric.")

    integration: ShopifyIntegration = get_instance(
        ctx,
        ShopifyIntegration,
        int(integration_id),
    )
    return {"shopify": serialize_shopify_integration(integration)}
