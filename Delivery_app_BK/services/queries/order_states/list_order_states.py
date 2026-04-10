from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_order_states import find_order_states
from .serialize_order_states import serialize_order_states


def list_order_states(ctx: ServiceContext):
    query = find_order_states(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 10))
    results = query.limit(limit).all()

    page_instances = results[:limit]

 

    serialized = serialize_order_states(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "order_states": serialized,
    }
