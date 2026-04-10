from Delivery_app_BK.models import (
    db, 
    UserRole,
    BaseRole,
    OrderStateTransitionRule,
    DateRangeAccessRule
)
from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets
from ...queries.get_instance import get_instance


def update_user_role(ctx: ServiceContext):
    relationship_map = {
        "base_role_id":BaseRole,
        "base_role":BaseRole,
        "date_range_access_rule": DateRangeAccessRule,
        "order_state_transition_rule": OrderStateTransitionRule,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        role: UserRole = get_instance(ctx=ctx, model=UserRole, value=target["target_id"])
        if role.is_system and not ctx.allow_is_system_modification:
            raise ValidationFailed("System roles cannot be updated.")
        instance = update_instance(ctx, UserRole, target["fields"], target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
