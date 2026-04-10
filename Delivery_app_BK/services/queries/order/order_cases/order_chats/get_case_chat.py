from Delivery_app_BK.models import CaseChat
from Delivery_app_BK.errors import NotFound

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from .serialize_case_chats import serialize_case_chats


def get_case_chat(order_chat_id: int, ctx: ServiceContext):
    found_chat = get_instance(
        ctx = ctx,
        model = CaseChat,
        value = order_chat_id
    )

    if not found_chat:
        raise NotFound(f"Order chat with id: {order_chat_id} does not exist.")

    serialized = serialize_case_chats(
        instances=[found_chat],
        ctx=ctx,
    )

    return {
        "case_chat": serialized[0] if isinstance(serialized, list) else serialized
    }
