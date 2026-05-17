from aiosmtplib import SMTP
from aiosmtplib.errors import SMTPAuthenticationError, SMTPConnectError, SMTPRecipientsRefused
from email.message import EmailMessage

from typing import TYPE_CHECKING

from Delivery_app_BK.services.utils.crypto import decrypt_secret

if TYPE_CHECKING:
    from Delivery_app_BK.models import EmailSMTP
    from Delivery_app_BK.models import MessageTemplate

class SMTPMixin:
    async def get_smtp_connection(self:"EmailSMTP"):

        try:
            smtp = SMTP(
                hostname = self.smtp_server,
                port = self.smtp_port,
                use_tls = self.use_ssl
            )

            await smtp.connect()
  
            # Upgrade to TLS if use_tls is True (STARTTLS)
            # STARTTLS only if requested and supported by the server
            if self.use_tls and "starttls" in smtp.esmtp_extensions:
                await smtp.starttls()
           
            password = decrypt_secret(self.smtp_password)
            await smtp.login(self.smtp_username, password)
            
            return smtp
        except Exception as exc:
            raise ConnectionError("SMTP verification failed.") from exc

    async def test_connection(self: "EmailSMTP"):
        smtp = await self.get_smtp_connection()
        await smtp.quit()


    def build_message(self:"EmailSMTP", client:dict, message_template:"MessageTemplate"):
        from Delivery_app_BK.models.tables.content_templates.message_template import SafeDict

        client_email = client.get('client_email')   
        if client_email is None:
            raise ValueError('Missing eamil.')

        def render_subject_value(value):
            if value is None:
                return ""
            if isinstance(value, str):
                return value.format_map(SafeDict(client))
            if isinstance(value, list):
                return "".join(render_subject_value(child) for child in value)
            if isinstance(value, dict):
                node_type = value.get("type")
                if node_type == "label":
                    label_key = value.get("labelKey") or value.get("label_key") or value.get("id")
                    return str(client.get(label_key, f"{{{label_key}}}")) if label_key else ""
                text_value = value.get("text")
                if isinstance(text_value, str):
                    return text_value.format_map(SafeDict(client))
                children = value.get("children")
                if isinstance(children, list):
                    return "".join(render_subject_value(child) for child in children)
            return ""

        subject = " ".join(
            (
                render_subject_value(getattr(message_template, "subject", None))
                or getattr(message_template, "name", "")
            )
            .replace("\r", " ")
            .replace("\n", " ")
            .split()
        )
        
        message = EmailMessage()
        message["From"] = self.smtp_username                
        message["To"] = client_email        
        message["Subject"] = subject     

        template:str = message_template.content   
        temp = template.format_map(SafeDict(client))  
        message.set_content(temp)
        

        return message
    

    async def batch_sender(
            self:"EmailSMTP", 
            target_clients, 
            message_template,
            successful_sent_messages:list,
            fail_sent_messages:list
    ):
        
        smtp = await self.get_smtp_connection()

        for client in target_clients:
            client_response = {
                    "id": client.get('id'),
                    'server_message': 'none'
                }
            try: 

                message = self.build_message(client,message_template)

                client:dict
                

                response:str
                response, response_message = await smtp.send_message(message)

                if not str(response_message).startswith("2."):
                    client_response['server_message'] = response_message
                    fail_sent_messages.append(client_response)
                else:
                    client_response['server_message'] = response_message
                    successful_sent_messages.append(client_response)

            except SMTPRecipientsRefused as e:
                client_response["error_type"] = str(e) 
                client_response["server_message"] = "invalid_recipient"
                fail_sent_messages.append(client_response)

            except SMTPAuthenticationError as e:
                client_response["error_type"] = str(e) 
                client_response["server_message"] = "auth_error"
                fail_sent_messages.append(client_response)

            except SMTPConnectError as e:
                client_response["error_type"] = str(e) 
                client_response["server_message"] = "connection_error"
                fail_sent_messages.append(client_response)

            except (Exception, ValueError) as e:
                client_response["error_type"] = "unknown_error"
                client_response["server_message"] = str(e) 
                fail_sent_messages.append(client_response)


        await smtp.quit()
    
    
