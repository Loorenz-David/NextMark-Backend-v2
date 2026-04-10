from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_date_range_access_rules import find_date_range_access_rules
from .serialize_date_range_access_rules import serialize_date_range_access_rules


def list_date_range_access_rules(ctx: ServiceContext):
    query = find_date_range_access_rules(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_date_range_access_rules(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "date_range_access_rules": serialized,
        "date_range_access_rules_pagination": pagination,
    }
