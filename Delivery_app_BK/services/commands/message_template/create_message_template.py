from sqlalchemy.exc import IntegrityError
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, Team, MessageTemplate
from Delivery_app_BK.services.domain.messaging import MESSAGE_PLAN_TYPES, validate_schedule_configuration
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result


MESSAGE_TEMPLATE_UNIQUE_CONSTRAINT = "uq_message_template_team_event_channel_plan_type"


def create_message_template(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []

    for field_set in extract_fields(ctx):
        # No default on purpose: a template that did not state its plan type
        # would silently land on local delivery and never reach pickup orders.
        if "plan_type" not in field_set:
            raise ValidationFailed(
                f"plan_type is required. Allowed values: {sorted(MESSAGE_PLAN_TYPES)}"
            )

        instance = create_instance(ctx, MessageTemplate, dict(field_set))
        validate_schedule_configuration(
            event_name=instance.event,
            offset_value=instance.schedule_offset_value,
            offset_unit=instance.schedule_offset_unit,
        )
        instances.append(instance)

    db.session.add_all(instances)
    # The unique constraint only fires on flush, so the duplicate check has to
    # wrap the flush rather than the instance construction.
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        if MESSAGE_TEMPLATE_UNIQUE_CONSTRAINT in str(e.orig):
            raise ValidationFailed(
                "A message template for the same team, event, channel and plan type already exists."
            )
        raise

    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
