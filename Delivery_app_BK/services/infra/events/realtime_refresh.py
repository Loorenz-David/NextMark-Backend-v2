from __future__ import annotations

from flask import current_app

from Delivery_app_BK.models import OrderEvent, db
from Delivery_app_BK.services.infra.jobs.realtime import enqueue_order_realtime_relay


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