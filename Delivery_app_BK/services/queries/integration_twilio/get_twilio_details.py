from Delivery_app_BK.models import TwilioMod
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance

from .serializers import serialize_twilio_integration


def get_twilio_details(ctx: ServiceContext, integration_id: str) -> dict:
    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: TwilioMod = get_instance(ctx, TwilioMod, lookup_id)
    return {"twilio": serialize_twilio_integration(integration)}
