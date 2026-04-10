from Delivery_app_BK.models import (
    db, 
    Team, 
    UserRole,
    BaseRole,
    OrderState,
    OrderStateTransitionRule,
    DateRangeAccessRule
)
from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result


def create_user_role(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
        "base_role_id":BaseRole,
        "base_role":BaseRole,
        "date_range_access_rule": DateRangeAccessRule,
        "order_state_transition_rule": OrderStateTransitionRule,
        "allowed_state_id": OrderState,
    }
    ctx.set_relationship_map(relationship_map)
    role_instances = []
    date_rule_instances = []
    state_rule_instances = []

    for field_set in extract_fields(ctx):
        if field_set.get("is_system") and not ctx.allow_is_system_modification:
            raise ValidationFailed("System roles cannot be created in this context.")

        if not field_set.get("base_role_id") and not field_set.get("base_role"):
            raise ValidationFailed("Missing base_role_id for user role creation.")

        date_rule_fields = field_set.pop("date_range_access_rule", None)
        state_rule_fields = field_set.pop("order_state_transition_rule", None)

        role_instance: UserRole = create_instance(ctx, UserRole, dict(field_set))
        role_instances.append(role_instance)

        if date_rule_fields:
            rule_fields = dict(date_rule_fields)
            rule_fields.pop("user_role_id", None)
            rule_instance = create_instance(ctx, DateRangeAccessRule, rule_fields)
            role_instance.date_range_access_rule = rule_instance
            date_rule_instances.append(rule_instance)

        if state_rule_fields:
            rule_fields = dict(state_rule_fields)
            rule_fields.pop("user_role_id", None)
            rule_instance = create_instance(ctx, OrderStateTransitionRule, rule_fields)
            role_instance.order_state_transition_rule = rule_instance
            state_rule_instances.append(rule_instance)

    db.session.add_all(role_instances)
    if date_rule_instances:
        db.session.add_all(date_rule_instances)
    if state_rule_instances:
        db.session.add_all(state_rule_instances)

    db.session.flush()

    role_results = build_create_result(ctx, role_instances)
    date_rule_results = (
        build_create_result(ctx, date_rule_instances)
        if date_rule_instances
        else None
    )
    state_rule_results = (
        build_create_result(ctx, state_rule_instances)
        if state_rule_instances
        else None
    )
    
    db.session.commit()

    result = {"user_role": role_results}
    if date_rule_results is not None:
        result["date_range_access_rule"] = date_rule_results
    if state_rule_results is not None:
        result["order_state_transition_rule"] = state_rule_results

    return result
