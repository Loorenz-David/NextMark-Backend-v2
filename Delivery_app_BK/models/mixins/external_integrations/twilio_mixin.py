import asyncio
from typing import TYPE_CHECKING
from twilio.rest import Client

from Delivery_app_BK.services.utils.crypto import decrypt_secret

if TYPE_CHECKING:
    from Delivery_app_BK.models.tables.integration_models.twilio_integration import TwilioMod
    from Delivery_app_BK.models.tables.content_templates.message_template import MessageTemplate


class SMSMixin:
    async def get_twilio_client(self: "TwilioMod") -> Client:

        """Initialize and return the Twilio client."""
        try:
            return Client(
                self.twilio_api_key_sid,
                decrypt_secret(self.twilio_api_key_secret_encrypted),
                account_sid=self.twilio_account_sid,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Twilio client: {str(e)}")


    def build_sms_message(self, client: dict, message_template: "MessageTemplate") -> str:

        """Format SMS content safely using SafeDict."""
        from Delivery_app_BK.models.tables.content_templates.message_template import SafeDict
        template:str = message_template.content
        body = template.format_map(SafeDict(client))

        return body

    async def batch_sender(
        self: "TwilioMod",
        target_clients: list,
        message_template: "MessageTemplate",
        successful_sent_messages: list,
        fail_sent_messages: list,
    ):
        """Send SMS messages to all clients."""
        twilio_client = await self.get_twilio_client()

        async def send_sms(client:dict):
            client_id:int =  client.get('id', None)
            try:
                phone:str = client.get('phone',None)
                
                if phone is None:
                    raise Exception (f"Missing to specify a phone number for client with id: {client_id}")

                body = self.build_sms_message(client, message_template)

                if '/' in phone :
                    for p in phone.split('/'):
                        message = await asyncio.to_thread(
                        twilio_client.messages.create,
                        body=body,
                        from_=self.sender_number,
                        to=p
                    )
                else:
                    message = await asyncio.to_thread(
                        twilio_client.messages.create,
                        body=body,
                        from_=self.sender_number,
                        to=phone
                    )

                client_response = {
                    "id": client_id,
                    "server_message": "sent",
                    "sid": message.sid
                }
                successful_sent_messages.append(client_response)

            except Exception as e:
                fail_sent_messages.append({
                    "id": client_id,
                    "error_type": str(e),
                    "server_message": "sms_send_error",
                })

        # send all messages concurrently but safely
        tasks = [send_sms(client) for client in target_clients]
        await asyncio.gather(*tasks)
