from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_facilities import find_facilities
from .serialize_facilities import serialize_facilities


def list_facilities(ctx: ServiceContext):
    query = find_facilities(ctx.query_params, ctx)
    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]
    pagination = build_id_pagination(page_instances=page_instances, has_more=has_more, ctx=ctx)
    serialized = serialize_facilities(instances=page_instances, ctx=ctx)
    return {"facilities": serialized, "facilities_pagination": pagination}
