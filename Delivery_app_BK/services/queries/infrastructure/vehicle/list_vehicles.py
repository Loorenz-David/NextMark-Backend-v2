from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_vehicles import find_vehicles
from .serialize_vehicles import serialize_vehicles


def list_vehicles(ctx: ServiceContext):
    query = find_vehicles(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_vehicles(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "vehicles": serialized,
        "vehicles_pagination": pagination,
    }
