from Delivery_app_BK.models import db, CaseChat, OrderCase

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import build_pagination
from .find_case_chats import find_case_chats
from .case_chats_stats import case_chats_stats
from .serialize_case_chats import serialize_case_chats


def list_case_chats(ctx: ServiceContext, order_id: int | None = None):
    base_query = db.session.query(CaseChat)
    if order_id is not None:
        base_query = base_query.join(OrderCase).filter(OrderCase.order_id == order_id)

    query = find_case_chats(
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

    serialized = serialize_case_chats(
        instances=page_instances,
        ctx=ctx,
    )

    stats = case_chats_stats(
        query=query,
        ctx=ctx,
    )

    return {
        "case_chats": serialized,
        "case_chats_pagination": pagination,
        "case_chats_stats": stats,
    }
