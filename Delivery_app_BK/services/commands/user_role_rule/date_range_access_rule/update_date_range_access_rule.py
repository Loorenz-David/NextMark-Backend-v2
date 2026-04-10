from Delivery_app_BK.models import db, DateRangeAccessRule, UserRole, Team

from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_date_range_access_rule(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
        "user_role_id": UserRole,
        "user_role": UserRole,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(
            ctx, DateRangeAccessRule, target["fields"], target["target_id"]
        )
        instances.append(instance.id)
    db.session.commit()
    return instances
