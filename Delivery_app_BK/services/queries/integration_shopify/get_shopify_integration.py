from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db, ShopifyIntegration

from ...context import ServiceContext


def get_integration(ctx: ServiceContext, shop: str):
    if not ctx.team_id:
        raise ValidationFailed("Team id is required to fetch Shopify integration.")
    if not shop:
        raise ValidationFailed("Shop is required to fetch Shopify integration.")

    normalized_shop = shop.strip()
    found_integration = (
        db.session.query(ShopifyIntegration)
        .filter(
            ShopifyIntegration.team_id == ctx.team_id,
            ShopifyIntegration.shop == normalized_shop,
        )
        .first()
    )

    if not found_integration:
        return None

    return found_integration

def get_integration_by_shop(shop:str):
    
    normalized_shop = shop.strip()

    found_integration = db.session.query(ShopifyIntegration).filter(
        ShopifyIntegration.shop == normalized_shop,
    ).first()

    return found_integration
