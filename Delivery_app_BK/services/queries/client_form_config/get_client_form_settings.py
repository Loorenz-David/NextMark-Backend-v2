from typing import Optional

from Delivery_app_BK.models import ClientFormSettings, db
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from .serialize_client_form_config import serialize_client_form_settings


def find_settings_for_team(team_id: int) -> Optional[ClientFormSettings]:
    """Return the team's settings row, or None when it has never been configured."""
    return (
        db.session.query(ClientFormSettings)
        .filter(ClientFormSettings.team_id == team_id)
        .one_or_none()
    )


def get_client_form_settings(ctx: ServiceContext):
    """Return the team's client-form settings, falling back to defaults.

    Teams have no settings row until they first save one, so an absent row is
    normal rather than an error — it serializes as the documented defaults.
    """
    team_id = require_team_id(ctx)
    settings = find_settings_for_team(team_id)

    return {"client_form_settings": serialize_client_form_settings(settings)}
