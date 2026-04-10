from Delivery_app_BK.services.commands.utils import build_create_result
import asyncio
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, EmailSMTP
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.utils import require_team_id
from Delivery_app_BK.services.utils.crypto import encrypt_secret


def connect_email(ctx: ServiceContext) -> dict:
    incoming_data = ctx.incoming_data or {}
    team_id = require_team_id(ctx)

    smtp_server = incoming_data.get("smtp_server")
    smtp_username = incoming_data.get("smtp_username")
    smtp_password = incoming_data.get("smtp_password")

   
    missing_fields = [
        field
        for field, value in {
            "smtp_server": smtp_server,
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
        }.items()
        if not value
    ]
    if missing_fields:
        raise ValidationFailed(
            f"Missing required fields: {', '.join(missing_fields)}."
        )

    client_id = incoming_data.get("client_id") or generate_client_id("email")
    smtp_port = incoming_data.get("smtp_port", 587)
    use_tls = incoming_data.get("use_tls", True)
    use_ssl = incoming_data.get("use_ssl", False)
    max_per_session = incoming_data.get("max_per_session", 50)
    encrypted_password = encrypt_secret(smtp_password)

    integration = EmailSMTP(
        client_id=client_id,
        team_id=team_id,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=encrypted_password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        max_per_session=max_per_session,
    )

    try:
        try:
            asyncio.run(integration.test_connection())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(integration.test_connection())
    except Exception as exc:
        raise ValidationFailed("SMTP verification failed") from exc

    db.session.add(integration)
    db.session.commit()

    result = build_create_result(ctx, [integration])
    return {"email": result}
