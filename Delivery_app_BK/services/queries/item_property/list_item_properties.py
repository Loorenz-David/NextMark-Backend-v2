from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_item_properties import find_item_properties
from .serialize_item_properties import serialize_item_properties


def list_item_properties(ctx: ServiceContext):
    query = find_item_properties(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_item_properties(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "item_properties": serialized,
        "item_properties_pagination": pagination,
    }
