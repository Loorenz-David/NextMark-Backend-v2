from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormMedia, Team, db
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets


def update_client_form_media(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})

    instance_ids = []
    for target in extract_targets(ctx):
        instance = update_instance(
            ctx, ClientFormMedia, target["fields"], target["target_id"]
        )
        instance_ids.append(instance.id)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if "uq_client_form_media_team_placement_position" in str(e.orig):
            raise ValidationFailed(
                "Client form media already occupies that position for this placement."
            )
        raise

    return instance_ids
