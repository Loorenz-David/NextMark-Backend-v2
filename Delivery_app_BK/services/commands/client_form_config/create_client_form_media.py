from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormMedia, Team, db
from Delivery_app_BK.services.domain.client_form.ordering import next_position
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import build_create_result, extract_fields


def create_client_form_media(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})
    team_id = require_team_id(ctx)

    # Positions are sequenced per placement, so each slot orders independently.
    taken_positions: dict[str, list[int]] = {}
    for placement, position in (
        db.session.query(ClientFormMedia.placement, ClientFormMedia.position)
        .filter(ClientFormMedia.team_id == team_id)
        .all()
    ):
        taken_positions.setdefault(placement, []).append(position)

    instances = []
    for field_set in extract_fields(ctx):
        fields = dict(field_set)
        placement = fields.get("placement")
        if fields.get("position") is None:
            fields["position"] = next_position(taken_positions.get(placement, []))
        taken_positions.setdefault(placement, []).append(fields["position"])

        instances.append(create_instance(ctx, ClientFormMedia, fields))

    db.session.add_all(instances)

    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        if "uq_client_form_media_team_placement_position" in str(e.orig):
            raise ValidationFailed(
                "Client form media already occupies that position for this placement."
            )
        raise

    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
