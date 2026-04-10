from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, EmailSMTP
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.utils.crypto import encrypt_secret

from Delivery_app_BK.services.queries.integration_email.serializers import (
    serialize_email_integration,
)


def update_email_config(ctx: ServiceContext, integration_id: str) -> dict:
    incoming_data = ctx.incoming_data or {}
    allowed_fields = {
        "smtp_server",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "use_tls",
        "use_ssl",
        "max_per_session",
    }

    update_fields = {
        key: value for key, value in incoming_data.items() if key in allowed_fields
    }
    if "smtp_password" in update_fields:
        update_fields["smtp_password"] = encrypt_secret(update_fields.pop("smtp_password"))
    if "smtp_password" in incoming_data:
        raise ValidationFailed("Encrypted SMTP passwords are not accepted from clients.")

    if not update_fields:
        raise ValidationFailed("No allowed fields provided to update email config.")

    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: EmailSMTP = get_instance(ctx, EmailSMTP, lookup_id)
    for field, value in update_fields.items():
        setattr(integration, field, value)

    db.session.commit()

    return {"email": serialize_email_integration(integration)}
