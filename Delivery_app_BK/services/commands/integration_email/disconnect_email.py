from Delivery_app_BK.models import db, EmailSMTP
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance


def disconnect_email(ctx: ServiceContext, integration_id: str) -> dict:
    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: EmailSMTP = get_instance(ctx, EmailSMTP, lookup_id)
    integration_id_value = integration.client_id or str(integration.id)
    db.session.delete(integration)
    db.session.commit()
    return {"email": {"id": integration_id_value}}
