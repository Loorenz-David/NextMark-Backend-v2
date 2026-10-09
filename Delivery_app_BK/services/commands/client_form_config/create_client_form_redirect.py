from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormRedirect, Team, db
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import build_create_result, extract_fields

MAX_REDIRECTS_PER_TEAM = 20

# A new page is never created active: activation goes through
# activate_client_form_redirect, which keeps the one-active-per-team rule.
EDITABLE_FIELDS = {"client_id", "label", "url"}


def create_client_form_redirect(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})
    team_id = require_team_id(ctx)

    field_sets = extract_fields(ctx)

    existing_count = (
        db.session.query(ClientFormRedirect)
        .filter(ClientFormRedirect.team_id == team_id)
        .count()
    )
    if existing_count + len(field_sets) > MAX_REDIRECTS_PER_TEAM:
        raise ValidationFailed(
            f"A team can save at most {MAX_REDIRECTS_PER_TEAM} redirect pages."
        )

    instances = []
    for field_set in field_sets:
        fields = {key: value for key, value in field_set.items() if key in EDITABLE_FIELDS}
        instances.append(create_instance(ctx, ClientFormRedirect, fields))

    db.session.add_all(instances)
    db.session.flush()

    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
