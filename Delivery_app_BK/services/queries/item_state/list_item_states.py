from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_item_states import find_item_states
from .serialize_item_states import serialize_item_states


def list_item_states(ctx: ServiceContext):
    query = find_item_states(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_item_states(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "item_states": serialized,
        "item_states_pagination": pagination,
    }
