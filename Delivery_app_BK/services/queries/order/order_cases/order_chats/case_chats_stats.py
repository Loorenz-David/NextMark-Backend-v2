from sqlalchemy import func
from sqlalchemy.orm import Query

from Delivery_app_BK.models import CaseChat

from Delivery_app_BK.services.context import ServiceContext


def case_chats_stats(query: Query, ctx: ServiceContext):
    query = query.order_by(None).limit(None).offset(None)

    total_chats = query.with_entities(
        func.count(CaseChat.id)
    ).scalar()

    return {
        "case_chats": {
            "total": total_chats
        }
    }
