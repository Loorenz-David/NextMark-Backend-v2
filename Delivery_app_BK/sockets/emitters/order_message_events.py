"""
Realtime frames for manually triggered order messaging.

Two frames per send request:
  - order_message.dispatched : once, when the request is accepted, listing every
                               target order and the actions queued for it.
  - order_message.updated    : once per action reaching SUCCESS / FAILED / SKIPPED.

Both are admin-only and carry their own notification_preview. Supplying the
preview matters: emit_business_event builds one when it is absent, and building
it loads the Order from the database, which would cost one query per frame.
No notify_* call is made on purpose — a bulk send would otherwise bury the
notification feed under one row per message.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from Delivery_app_BK.services.domain.user import ADMIN_APP_SCOPE
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ORDER_MESSAGE_DISPATCHED,
    BUSINESS_EVENT_ORDER_MESSAGE_UPDATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room


_STATUS_TITLES = {
    "SUCCESS": "Message sent",
    "FAILED": "Message failed",
    "SKIPPED": "Message not sent",
}


def _emit(*, team_id: int, envelope: dict) -> None:
    """
    Socket delivery must never fail the send it is reporting on: the message is
    already queued or delivered by the time these frames go out.
    """
    try:
        emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    except Exception as exc:
        current_app.logger.warning(
            "Failed to emit %s for team %s: %s",
            envelope.get("event_name"),
            team_id,
            str(exc),
        )


def emit_order_message_dispatched(
    *,
    team_id: int,
    request_id: str,
    template_event: str,
    channels: list[str],
    requested_by: int | None,
    orders: list[dict[str, Any]],
    not_found_order_ids: list[int],
    plan_types: dict[str, list[str]] | None = None,
    skipped_orders: list[dict[str, Any]] | None = None,
) -> None:
    total_actions = sum(len(order.get("actions") or []) for order in orders)

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ORDER_MESSAGE_DISPATCHED,
        team_id=team_id,
        entity_type="order_message_request",
        entity_id=None,
        app_scopes=[ADMIN_APP_SCOPE],
        payload={
            "request_id": request_id,
            "template_event": template_event,
            "channels": list(channels),
            # Per plan type, which channels had an enabled template. `channels`
            # above is the union, kept for clients that predate the breakdown.
            "plan_types": {key: list(value) for key, value in (plan_types or {}).items()},
            "requested_by": requested_by,
            "total_actions": total_actions,
            "orders": orders,
            "not_found_order_ids": list(not_found_order_ids),
            "skipped_orders": list(skipped_orders or []),
            "notification_preview": {
                "kind": BUSINESS_EVENT_ORDER_MESSAGE_DISPATCHED,
                "title": "Messages queued",
                "description": f"{template_event} queued for {len(orders)} order(s).",
            },
        },
    )
    _emit(team_id=team_id, envelope=envelope)


def emit_order_message_updated(
    *,
    team_id: int,
    order_id: int | None,
    event_id: int,
    action_id: int,
    request_id: str | None,
    template_event: str,
    channel: str | None,
    status: str,
    last_error: str | None,
    processed_at: str | None,
) -> None:
    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ORDER_MESSAGE_UPDATED,
        team_id=team_id,
        entity_type="order",
        entity_id=order_id,
        app_scopes=[ADMIN_APP_SCOPE],
        payload={
            "request_id": request_id,
            "order_id": order_id,
            "event_id": event_id,
            "action_id": action_id,
            "template_event": template_event,
            "channel": channel,
            "status": status,
            "last_error": last_error,
            "processed_at": processed_at,
            "notification_preview": {
                "kind": BUSINESS_EVENT_ORDER_MESSAGE_UPDATED,
                "title": _STATUS_TITLES.get(status, "Message updated"),
                "description": f"{template_event} · {channel or 'unknown channel'}",
            },
        },
    )
    _emit(team_id=team_id, envelope=envelope)
