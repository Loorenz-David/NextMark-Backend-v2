from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormRule, Team, db
from Delivery_app_BK.services.domain.client_form.ordering import next_position
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import build_create_result, extract_fields


def create_client_form_rule(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team, "team": Team})
    team_id = require_team_id(ctx)

    taken_positions = [
        row[0]
        for row in db.session.query(ClientFormRule.position)
        .filter(ClientFormRule.team_id == team_id)
        .all()
    ]

    instances = []
    for field_set in extract_fields(ctx):
        fields = dict(field_set)
        # Append to the end unless the caller pinned a position explicitly.
        if fields.get("position") is None:
            fields["position"] = next_position(taken_positions)
        taken_positions.append(fields["position"])

        instances.append(create_instance(ctx, ClientFormRule, fields))

    db.session.add_all(instances)

    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        if "uq_client_form_rule_team_position" in str(e.orig):
            raise ValidationFailed(
                "A client form rule already occupies that position for this team."
            )
        raise

    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
