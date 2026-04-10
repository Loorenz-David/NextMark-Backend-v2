from __future__ import annotations

from typing import Protocol

from Delivery_app_BK.models import TwilioMod
from Delivery_app_BK.services.utils.crypto import decrypt_secret


class SMSProvider(Protocol):
    def validate_connection(self) -> None: ...

    def send_message(self, to_number: str, body: str) -> str | None: ...


class TwilioSMSProvider:
    def __init__(self, integration: TwilioMod) -> None:
        self.integration = integration
        self._client = None

    def _get_client(self):

        if self._client is not None:

            return self._client

        try:
            from twilio.rest import Client
        except Exception as exc:
            raise RuntimeError("Twilio SDK is not installed.") from exc

        api_key_secret = decrypt_secret(self.integration.twilio_api_key_secret_encrypted)

        self._client = Client(
            self.integration.twilio_api_key_sid,
            api_key_secret,
            account_sid=self.integration.twilio_account_sid,
        )
        
        return self._client

    def validate_connection(self) -> None:

        client = self._get_client()

        try:
            result = client.api.accounts(self.integration.twilio_account_sid).fetch()
        except Exception as exc:
            
            raise RuntimeError("Failed to validate Twilio credentials.") from exc

    def send_message(self, to_number: str, body: str) -> str | None:
        client = self._get_client()
        message = client.messages.create(
            body=body,
            from_=self.integration.sender_number,
            to=to_number,
        )
        return getattr(message, "sid", None)


def build_sms_provider(integration: TwilioMod) -> SMSProvider:
    return TwilioSMSProvider(integration)
