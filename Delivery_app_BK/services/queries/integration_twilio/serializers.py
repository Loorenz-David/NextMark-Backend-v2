from Delivery_app_BK.models import TwilioMod


def serialize_twilio_integration(instance: TwilioMod) -> dict:
    return {
        "id": instance.client_id or str(instance.id),
        "client_id": instance.client_id,
        "twilio_account_sid": instance.twilio_account_sid,
        "twilio_api_key_sid": instance.twilio_api_key_sid,
        "sender_number": instance.sender_number,
    }
