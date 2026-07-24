from __future__ import annotations

from flask import current_app

from Delivery_app_BK.models import OrderEvent, db
from Delivery_app_BK.services.domain.messaging import MANUAL_ACTION_SCOPE
from Delivery_app_BK.services.infra.jobs.realtime import enqueue_order_realtime_relay


def notify_order_action_changed(action) -> None:
    """
    Publishes a status change on an order event action.

    Manual sends are pushed straight to the admin room: their event is never
    dispatched through the event bus, so the generic relay would enqueue a job
    that fans out nothing. Automatic actions keep the relay, which carries the
    business event their order listeners already subscribe to.
    """
    if getattr(action, "action_scope", "") != MANUAL_ACTION_SCOPE:
        notify_order_event_history_changed(getattr(action, "event_id", None))
        return

    from Delivery_app_BK.sockets.emitters.order_message_events import emit_order_message_updated

    payload = getattr(action, "payload", None)
    payload = payload if isinstance(payload, dict) else {}
    event = getattr(action, "event", None)

    team_id = getattr(action, "team_id", None) or getattr(event, "team_id", None)
    if team_id is None:
        return

    processed_at = getattr(action, "processed_at", None)

    emit_order_message_updated(
        team_id=team_id,
        order_id=getattr(event, "order_id", None),
        event_id=getattr(action, "event_id", None),
        action_id=getattr(action, "id", None),
        request_id=payload.get("request_id"),
        template_event=payload.get("template_event") or getattr(event, "event_name", ""),
        channel=payload.get("channel"),
        status=getattr(action, "status", ""),
        last_error=getattr(action, "last_error", None),
        processed_at=processed_at.isoformat() if processed_at else None,
    )


def notify_order_event_history_changed(order_event_id: int | None) -> None:
    if not order_event_id:
        return

    event_row = db.session.get(OrderEvent, order_event_id)
    if event_row is None:
        return

    # Invalidate idempotency marker so realtime relay can fan out fresh action state.
    event_row.relayed_at = None
    db.session.commit()

    try:
        enqueue_order_realtime_relay(event_row.id)
    except Exception as exc:
        current_app.logger.warning(
            "Failed to enqueue order realtime relay for event id %s: %s",
            event_row.id,
            str(exc),
        )