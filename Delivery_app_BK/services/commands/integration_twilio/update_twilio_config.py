from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, TwilioMod
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.messaging.sms_provider import build_sms_provider
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.utils.crypto import encrypt_secret

from Delivery_app_BK.services.queries.integration_twilio.serializers import (
    serialize_twilio_integration,
)


def update_twilio_config(ctx: ServiceContext, integration_id: str) -> dict:
    incoming_data = ctx.incoming_data or {}
    allowed_fields = {
        "twilio_account_sid",
        "twilio_api_key_sid",
        "twilio_api_key_secret",
        "sender_number",
    }

    update_fields = {
        key: value for key, value in incoming_data.items() if key in allowed_fields
    }
    if "twilio_api_key_secret" in update_fields:
        update_fields["twilio_api_key_secret_encrypted"] = encrypt_secret(
            str(update_fields.pop("twilio_api_key_secret"))
        )

    if not update_fields:
        raise ValidationFailed("No allowed fields provided to update Twilio config.")

    lookup_id = int(integration_id) if integration_id.isdigit() else integration_id
    integration: TwilioMod = get_instance(ctx, TwilioMod, lookup_id)
    for field, value in update_fields.items():
        setattr(integration, field, value)

    try:
        provider = build_sms_provider(integration)
        provider.validate_connection()
    except Exception as exc:
        raise ValidationFailed("Twilio credential verification failed.") from exc

    db.session.commit()

    return {"twilio": serialize_twilio_integration(integration)}
