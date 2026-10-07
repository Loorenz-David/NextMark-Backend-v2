from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, EmailSMTP
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.utils.crypto import decrypt_secret, encrypt_secret

from Delivery_app_BK.services.queries.integration_email.serializers import (
    serialize_email_integration,
)


def _is_encrypted_secret(value: str) -> bool:
    """A value that decrypts with our key was produced by us, never typed by a client."""
    try:
        decrypt_secret(value)
    except ValueError:
        return False
    return True


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
        raw_password = update_fields["smtp_password"]
        if not isinstance(raw_password, str) or not raw_password.strip():
            raise ValidationFailed("SMTP password must be a non-empty string.")
        # Clients always send the plain app password; a stored ciphertext echoed
        # back would otherwise be encrypted a second time and break login.
        if _is_encrypted_secret(raw_password):
            raise ValidationFailed("Encrypted SMTP passwords are not accepted from clients.")
        update_fields["smtp_password"] = encrypt_secret(raw_password)

    if not update_fields:
        raise ValidationFailed("No allowed fields provided to update email config.")

    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: EmailSMTP = get_instance(ctx, EmailSMTP, lookup_id)
    for field, value in update_fields.items():
        setattr(integration, field, value)

    db.session.commit()

    return {"email": serialize_email_integration(integration)}
