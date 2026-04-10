from Delivery_app_BK.models import db, DateRangeAccessRule, OrderStateTransitionRule
from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_date_range_access_rules import find_date_range_access_rules
from .find_order_state_transition_rules import find_order_state_transition_rules
from .serialize_date_range_access_rules import serialize_date_range_access_rules
from .serialize_order_state_transition_rules import (
    serialize_order_state_transition_rules,
)


def list_user_role_rules(ctx: ServiceContext, user_role_id: int | None = None):
    if user_role_id is not None and not isinstance(user_role_id, int):
        raise ValidationFailed("user_role_id must be an integer.")

    base_date_query = db.session.query(DateRangeAccessRule)
    base_state_query = db.session.query(OrderStateTransitionRule)

    if user_role_id is not None:
        base_date_query = base_date_query.filter(
            DateRangeAccessRule.user_role_id == user_role_id
        )
        base_state_query = base_state_query.filter(
            OrderStateTransitionRule.user_role_id == user_role_id
        )

    date_query = find_date_range_access_rules(
        params=ctx.query_params,
        ctx=ctx,
        query=base_date_query,
    )
    state_query = find_order_state_transition_rules(
        params=ctx.query_params,
        ctx=ctx,
        query=base_state_query,
    )

    limit = int(ctx.query_params.get("limit", 50))

    date_results = date_query.limit(limit + 1).all()
    date_has_more = len(date_results) > limit
    date_page = date_results[:limit]

    state_results = state_query.limit(limit + 1).all()
    state_has_more = len(state_results) > limit
    state_page = state_results[:limit]

    date_pagination = build_id_pagination(
        page_instances=date_page,
        has_more=date_has_more,
        ctx=ctx,
    )
    state_pagination = build_id_pagination(
        page_instances=state_page,
        has_more=state_has_more,
        ctx=ctx,
    )

    date_serialized = serialize_date_range_access_rules(
        instances=date_page,
        ctx=ctx,
    )
    state_serialized = serialize_order_state_transition_rules(
        instances=state_page,
        ctx=ctx,
    )

    return {
        "date_range_access_rules": date_serialized,
        "date_range_access_rules_pagination": date_pagination,
        "order_state_transition_rules": state_serialized,
        "order_state_transition_rules_pagination": state_pagination,
    }
