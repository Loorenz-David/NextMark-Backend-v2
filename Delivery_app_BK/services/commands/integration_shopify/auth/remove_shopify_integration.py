from Delivery_app_BK.models import db, ShopifyIntegration
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.integration_shopify import get_integration_by_shop


def handle_shopify_unisntall(shop:str) -> None:

    shop_integration = get_integration_by_shop(shop)

    if not shop_integration:
        return

   

    db.session.delete(shop_integration)
    db.session.commit()


def remove_shopify_integration(ctx: ServiceContext, integration_id: str) -> None:
    integration: ShopifyIntegration = get_instance(
        ctx,
        ShopifyIntegration,
        int(integration_id),
    )

    db.session.delete(integration)
    db.session.commit()
