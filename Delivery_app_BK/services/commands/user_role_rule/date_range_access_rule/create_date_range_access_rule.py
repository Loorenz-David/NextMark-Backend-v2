from Delivery_app_BK.models import db, DateRangeAccessRule, UserRole, Team
from Delivery_app_BK.errors import ValidationFailed

from ....context import ServiceContext
from ...base.create_instance import create_instance
from ...utils import extract_fields, build_create_result


def create_date_range_access_rule(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
        "user_role_id": UserRole,
        "user_role": UserRole,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []

    for field_set in extract_fields(ctx):
        if "user_role_id" not in field_set:
            raise ValidationFailed(
                "Missing user_role_id for date_range_access_rule creation."
            )
        instance = create_instance(ctx, DateRangeAccessRule, dict(field_set))
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
