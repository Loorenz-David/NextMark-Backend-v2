from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, EmailSMTP


def list_email_integration_ids(team_id: int) -> list[dict]:
    if not team_id:
        raise ValidationFailed("Team id is required to list email integrations.")

    integrations = (
        db.session.query(EmailSMTP)
        .filter(EmailSMTP.team_id == team_id)
        .all()
    )

    return [{"id": integration.id} for integration in integrations]
