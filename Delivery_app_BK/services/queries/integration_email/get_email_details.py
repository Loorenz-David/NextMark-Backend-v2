from Delivery_app_BK.models import EmailSMTP
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance

from .serializers import serialize_email_integration


def get_email_details(ctx: ServiceContext, integration_id: str) -> dict:
    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: EmailSMTP = get_instance(ctx, EmailSMTP, lookup_id)
    return {"email": serialize_email_integration(integration)}
