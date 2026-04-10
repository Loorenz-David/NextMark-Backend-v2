from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.integrations.email_repository import (
    list_email_integration_ids,
)
from Delivery_app_BK.services.queries.integrations.shopify_repository import (
    list_shopify_integration_ids,
)
from Delivery_app_BK.services.queries.integrations.twilio_repository import (
    list_twilio_integration_ids,
)


def list_active_integrations(ctx: ServiceContext) -> dict:
    if not ctx.team_id:
        raise ValidationFailed("Team id is required to list integrations.")

    shopify_ids = list_shopify_integration_ids(ctx.team_id)
    email_ids = list_email_integration_ids(ctx.team_id)
    twilio_ids = list_twilio_integration_ids(ctx.team_id)

    return {
        "shopify": shopify_ids[0]["id"] if shopify_ids else None,
        "email": email_ids[0]["id"] if email_ids else None,
        "twilio": twilio_ids[0]["id"] if twilio_ids else None,
    }
