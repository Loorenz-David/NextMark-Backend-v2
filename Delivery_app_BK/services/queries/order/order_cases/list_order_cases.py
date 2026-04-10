from Delivery_app_BK.models import db, OrderCase

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import build_pagination
from .find_order_cases import find_order_cases
from .order_cases_stats import order_cases_stats
from .serialize_order_cases import serialize_order_cases


def list_order_cases(ctx: ServiceContext, order_id: int | None = None):
    base_query = db.session.query(OrderCase)
    if order_id is not None:
        base_query = base_query.filter(OrderCase.order_id == order_id)

    query = find_order_cases(
        params=ctx.query_params,
        ctx=ctx,
        query=base_query,
    )

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_pagination(
        page_instances=page_instances,
        has_more=has_more,
        date_attr="creation_date",
        id_attr="id",
        ctx=ctx,
    )

    serialized = serialize_order_cases(
        instances=page_instances,
        ctx=ctx,
    )

    stats = order_cases_stats(
        query=query,
        ctx=ctx,
    )

    return {
        "order_cases": serialized,
        "order_cases_pagination": pagination,
        "order_cases_stats": stats,
    }
