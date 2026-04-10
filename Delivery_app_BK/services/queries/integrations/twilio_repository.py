from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, TwilioMod


def list_twilio_integration_ids(team_id: int) -> list[dict]:
    if not team_id:
        raise ValidationFailed("Team id is required to list Twilio integrations.")

    integrations = (
        db.session.query(TwilioMod)
        .filter(TwilioMod.team_id == team_id)
        .all()
    )

    return [{"id": integration.id} for integration in integrations]
