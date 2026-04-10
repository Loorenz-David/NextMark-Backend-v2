from Delivery_app_BK.models import db, MessageTemplate, Team
from Delivery_app_BK.services.domain.messaging import validate_schedule_configuration
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets


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
    db.session.commit()
    return instances
