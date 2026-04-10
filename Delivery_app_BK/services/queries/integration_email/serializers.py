from Delivery_app_BK.models import EmailSMTP


def serialize_email_integration(instance: EmailSMTP) -> dict:
    return {
        "id": instance.client_id or str(instance.id),
        "client_id": instance.client_id,
        "smtp_server": instance.smtp_server,
        "smtp_port": instance.smtp_port,
        "smtp_username": instance.smtp_username,
        "use_tls": instance.use_tls,
        "use_ssl": instance.use_ssl,
        "max_per_session": instance.max_per_session,
    }
