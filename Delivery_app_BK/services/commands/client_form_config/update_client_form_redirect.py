from Delivery_app_BK.models import ClientFormRedirect, Team, db
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets

# `is_active` is changed only by activate_client_form_redirect.
EDITABLE_FIELDS = {"label", "url"}


def update_client_form_redirect(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})

    instance_ids = []
    for target in extract_targets(ctx):
        fields = {
            key: value
            for key, value in (target.get("fields") or {}).items()
            if key in EDITABLE_FIELDS
        }
        instance = update_instance(ctx, ClientFormRedirect, fields, target["target_id"])
        instance_ids.append(instance.id)

    db.session.commit()
    return instance_ids
