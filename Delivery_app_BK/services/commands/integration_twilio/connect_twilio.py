from Delivery_app_BK.services.commands.utils.build_create_result import build_create_result
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, TwilioMod
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.infra.messaging.sms_provider import build_sms_provider
from Delivery_app_BK.services.utils import require_team_id
from Delivery_app_BK.services.utils.crypto import encrypt_secret

from Delivery_app_BK.services.queries.integration_twilio.serializers import (
    serialize_twilio_integration,
)


def connect_twilio(ctx: ServiceContext) -> dict:
    incoming_data = ctx.incoming_data or {}
    team_id = require_team_id(ctx)

    twilio_account_sid = incoming_data.get("twilio_account_sid")
    twilio_api_key_sid = incoming_data.get("twilio_api_key_sid")
    twilio_api_key_secret = incoming_data.get("twilio_api_key_secret")
    sender_number = incoming_data.get("sender_number")

    missing_fields = [
        field
        for field, value in {
            "twilio_account_sid": twilio_account_sid,
            "twilio_api_key_sid": twilio_api_key_sid,
            "twilio_api_key_secret": twilio_api_key_secret,
            "sender_number": sender_number,
        }.items()
        if not value
    ]
    if missing_fields:
        raise ValidationFailed(
            f"Missing required fields: {', '.join(missing_fields)}."
        )

    client_id = incoming_data.get("client_id") or generate_client_id("twilio")
    encrypted_api_key_secret = encrypt_secret(str(twilio_api_key_secret))

    integration = TwilioMod(
        client_id=client_id,
        team_id=team_id,
        twilio_account_sid=str(twilio_account_sid),
        twilio_api_key_sid=str(twilio_api_key_sid),
        twilio_api_key_secret_encrypted=encrypted_api_key_secret,
        sender_number=str(sender_number),
    )

    try:
        provider = build_sms_provider(integration)
        provider.validate_connection()
    except Exception as exc:
        raise ValidationFailed("Twilio credential verification failed.") from exc

    db.session.add(integration)
    db.session.commit()
    
    result = build_create_result(ctx, [integration])
    return {"twilio":result}
