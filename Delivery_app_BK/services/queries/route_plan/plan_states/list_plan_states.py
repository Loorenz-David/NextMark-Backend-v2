from Delivery_app_BK.services.context import ServiceContext

from ...utils import build_id_pagination
from .find_plan_states import find_plan_states
from .serialize_plan_states import serialize_plan_states


def list_plan_states(ctx: ServiceContext):
    query = find_plan_states(ctx.query_params, ctx)
    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_plan_states(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "plan_states": serialized,
        "plan_states_pagination": pagination,
    }
