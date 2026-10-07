from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, MessageTemplate, Team
from Delivery_app_BK.services.domain.messaging import validate_schedule_configuration
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets


MESSAGE_TEMPLATE_UNIQUE_CONSTRAINT = "uq_message_template_team_event_channel_plan_type"


def update_message_template(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(ctx, MessageTemplate, target["fields"], target["target_id"])
        validate_schedule_configuration(
            event_name=instance.event,
            offset_value=instance.schedule_offset_value,
            offset_unit=instance.schedule_offset_unit,
        )
        instances.append(instance.id)

    # Moving a template onto an (event, channel, plan_type) another row already
    # owns only surfaces when the session flushes, so the check belongs here.
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        if MESSAGE_TEMPLATE_UNIQUE_CONSTRAINT in str(e.orig):
            raise ValidationFailed(
                "A message template for the same team, event, channel and plan type already exists."
            )
        raise

    db.session.commit()
    return instances
