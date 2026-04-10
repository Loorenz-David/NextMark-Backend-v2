from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_order_state_transition_rules import find_order_state_transition_rules
from .serialize_order_state_transition_rules import (
    serialize_order_state_transition_rules,
)


def list_order_state_transition_rules(ctx: ServiceContext):
    query = find_order_state_transition_rules(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_order_state_transition_rules(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "order_state_transition_rules": serialized,
        "order_state_transition_rules_pagination": pagination,
    }
