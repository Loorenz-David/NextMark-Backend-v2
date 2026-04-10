from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_item_types import find_item_types
from .serialize_item_types import serialize_item_types


def list_item_types(ctx: ServiceContext):
    query = find_item_types(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_item_types(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "item_types": serialized,
        "item_types_pagination": pagination,
    }
