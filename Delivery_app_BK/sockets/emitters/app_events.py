from __future__ import annotations

from Delivery_app_BK.models import AppEventOutbox
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ORDER_CASE_CREATED,
    BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED,
    BUSINESS_EVENT_ORDER_CASE_UPDATED,
    BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.notifications import notify_app_event
from Delivery_app_BK.sockets.emitters.route_orders import emit_route_order_event
from Delivery_app_BK.sockets.rooms.names import build_order_chat_room, build_team_admin_room


def fanout_app_event(event_row: AppEventOutbox) -> None:
    if not event_row.team_id:
        return

    payload = dict(event_row.payload or {})
    entity_id = int(event_row.entity_id) if str(event_row.entity_id).isdigit() else None
    order_id = payload.get("order_id")
    if not isinstance(order_id, int) and isinstance(order_id, str) and order_id.isdigit():
        order_id = int(order_id)

    envelope = build_business_event_envelope(
        event_id=event_row.event_id,
        event_name=event_row.event_name,
        occurred_at=event_row.occurred_at,
        team_id=event_row.team_id,
        entity_type=str(event_row.entity_type or "app_event"),
        entity_id=entity_id,
        payload=payload,
    )

    if event_row.event_name in {
        BUSINESS_EVENT_ORDER_CASE_CREATED,
        BUSINESS_EVENT_ORDER_CASE_UPDATED,
        BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED,
    }:
        emit_business_event(
            room=build_team_admin_room(event_row.team_id),
            envelope=envelope,
        )
        emit_route_order_event(
            team_id=event_row.team_id,
            order_id=order_id,
            envelope=envelope,
        )
        notify_app_event(
            event_id=event_row.event_id,
            event_name=event_row.event_name,
            team_id=event_row.team_id,
            entity_type=str(event_row.entity_type or "app_event"),
            entity_id=entity_id,
            payload=payload,
            occurred_at=event_row.occurred_at,
            actor=event_row.actor,
        )
        return

    if event_row.event_name == BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED and order_id is not None:
        emit_business_event(
            room=build_team_admin_room(event_row.team_id),
            envelope=envelope,
        )
        emit_business_event(
            room=build_order_chat_room(event_row.team_id, order_id),
            envelope=envelope,
        )
        emit_route_order_event(
            team_id=event_row.team_id,
            order_id=order_id,
            envelope=envelope,
        )
        notify_app_event(
            event_id=event_row.event_id,
            event_name=event_row.event_name,
            team_id=event_row.team_id,
            entity_type=str(event_row.entity_type or "app_event"),
            entity_id=entity_id,
            payload=payload,
            occurred_at=event_row.occurred_at,
            actor=event_row.actor,
        )
