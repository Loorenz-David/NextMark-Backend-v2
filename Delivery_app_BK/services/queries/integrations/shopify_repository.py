from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, ShopifyIntegration


def list_shopify_integration_ids(team_id: int) -> list[dict]:
    if not team_id:
        raise ValidationFailed("Team id is required to list Shopify integrations.")

    integrations = (
        db.session.query(ShopifyIntegration)
        .filter(ShopifyIntegration.team_id == team_id)
        .all()
    )

    return [{"id": integration.id} for integration in integrations]
