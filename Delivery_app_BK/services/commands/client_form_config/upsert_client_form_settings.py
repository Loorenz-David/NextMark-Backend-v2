"""Create or update the team's client-form settings singleton.

Not a plain create_instance: exactly one row may exist per team
(uq_client_form_settings_team), so this fetches the existing row when present
and only inserts on first save.
"""

from Delivery_app_BK.models import ClientFormSettings, Team, db
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields
from ..utils.inject_fields import inject_fields

EDITABLE_FIELDS = {
    "terms_enabled",
    "require_acceptance",
    "show_rules",
    "show_media",
}


def upsert_client_form_settings(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})

    team_id = require_team_id(ctx)
    field_sets = extract_fields(ctx)
    fields = field_sets[0] if field_sets else {}

    safe_fields = {key: value for key, value in fields.items() if key in EDITABLE_FIELDS}

    instance = (
        db.session.query(ClientFormSettings)
        .filter(ClientFormSettings.team_id == team_id)
        .one_or_none()
    )

    if instance is None:
        instance = create_instance(ctx, ClientFormSettings, safe_fields)
        db.session.add(instance)
    else:
        inject_fields(ctx, instance, safe_fields)

    db.session.flush()
    settings_id = instance.id
    db.session.commit()

    return {"id": settings_id}
