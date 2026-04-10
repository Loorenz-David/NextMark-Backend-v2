from Delivery_app_BK.models import CaseChat
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.emitters.route_orders import emit_route_order_event
from Delivery_app_BK.sockets.rooms.names import build_order_chat_room, build_team_admin_room


def _resolve_user_name(case_chat: CaseChat) -> str | None:
    if isinstance(case_chat.user_name, str) and case_chat.user_name.strip():
        return case_chat.user_name.strip()

    user = case_chat.user
    if user is not None:
        username = getattr(user, "username", None)
        if isinstance(username, str) and username.strip():
            return username.strip()

        email = getattr(user, "email", None)
        if isinstance(email, str) and email.strip():
            return email.strip()

    return None


def emit_order_chat_message_created(case_chat: CaseChat) -> None:
    order_case = case_chat.order_case
    order = order_case.order if order_case else None
    team_id = order.team_id if order else None
    order_id = order.id if order else None
    if team_id is None or order_id is None:
        return

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED,
        occurred_at=case_chat.creation_date,
        team_id=team_id,
        entity_type="order_chat",
        entity_id=case_chat.id,
        payload={
            "chat_id": case_chat.id,
            "chat_client_id": case_chat.client_id,
            "message": case_chat.message,
            "order_case_id": case_chat.order_case_id,
            "order_case_client_id": order_case.client_id if order_case else None,
            "order_id": order_id,
            "user_id": case_chat.user_id,
            "user_name": _resolve_user_name(case_chat),
        },
    )

    emit_business_event(
        room=build_team_admin_room(team_id),
        envelope=envelope,
    )
    emit_business_event(
        room=build_order_chat_room(team_id, order_id),
        envelope=envelope,
    )
    emit_route_order_event(
        team_id=team_id,
        order_id=order_id,
        envelope=envelope,
    )
