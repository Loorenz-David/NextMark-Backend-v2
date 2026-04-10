from Delivery_app_BK.models import db, CaseChat, NotificationRead
from Delivery_app_BK.errors import ValidationFailed

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import build_pagination
from .find_case_chats import find_case_chats
from .case_chats_stats import case_chats_stats
from .serialize_case_chats import serialize_case_chats


def list_unseen_case_chats(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to fetch unseen chats.")

    base_query = db.session.query(CaseChat).filter(
        CaseChat.user_id != ctx.user_id,
        ~CaseChat.notification_reads.any(NotificationRead.user_id == ctx.user_id)
    )

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
