from sqlalchemy.exc import IntegrityError
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, Team, MessageTemplate
from Delivery_app_BK.services.domain.messaging import validate_schedule_configuration
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result


def create_message_template(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    
    for field_set in extract_fields(ctx):
        try:
           
            instance = create_instance(ctx, MessageTemplate, dict(field_set))
            validate_schedule_configuration(
                event_name=instance.event,
                offset_value=instance.schedule_offset_value,
                offset_unit=instance.schedule_offset_unit,
            )
        except IntegrityError as e:
            db.session.rollback()
            if "uq_message_template_team_event_channel" in str(e.orig):
                raise ValidationFailed(
                    "A message template with in the same team, event, and channel already exists."
                )
            else:
                raise
            
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
