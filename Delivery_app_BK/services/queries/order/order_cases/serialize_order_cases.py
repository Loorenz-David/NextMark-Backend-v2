from typing import Type, List
from flask_sqlalchemy.model import Model
from Delivery_app_BK.models import OrderCase
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import map_return_values
from Delivery_app_BK.services.queries.order.order_cases.order_chats.serialize_case_chats import (
    unpack_case_chats,
)


def _count_unseen_chats(chats: list, user_id: int | None) -> int:
    if not user_id:
        return 0
    
    total = sum(
        1
        for chat in chats
        if not any(read.user_id == user_id for read in (chat.notification_reads or []))
    )
    
    return total


def serialize_order_cases(instances: List[OrderCase], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        creation_date = instance.creation_date
        chats = instance.chats or []
        user_id = ctx.identity.get("user_id") if ctx.identity else None
        unpacked = {
            "id": instance.id,
            "state": instance.state,
            "creation_date": creation_date.isoformat() if creation_date else None,
            "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
            "order_id": instance.order_id,
            "label": instance.label,
            "created_by": instance.created_by,
            "chats": unpack_case_chats(chats),
            "unseen_chats": _count_unseen_chats(chats, user_id),
            "order_reference": instance.order.reference_number or 'undefined reference number'
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "order_case")
