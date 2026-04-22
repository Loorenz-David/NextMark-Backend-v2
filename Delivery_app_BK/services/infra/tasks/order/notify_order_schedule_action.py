from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import OrderEventAction, db
from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order.notify_order_schedule import (
    notify_order_schedule,
)
from Delivery_app_BK.services.infra.events.realtime_refresh import (
    notify_order_event_history_changed,
)


def _truncate_error(error_message: str) -> str:
    if len(error_message) <= 3000:
        return error_message
    return error_message[:3000]


def _mark_action_failed(action: OrderEventAction, error_message: str) -> None:
    action.status = OrderEventAction.STATUS_FAILED
    action.last_error = _truncate_error(error_message)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def _mark_action_success(action: OrderEventAction) -> None:
    action.status = OrderEventAction.STATUS_SUCCESS
    action.last_error = None
    action.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def _mark_action_skipped(action: OrderEventAction, reason: str) -> None:
    action.status = OrderEventAction.STATUS_SKIPPED
    action.last_error = _truncate_error(reason)
    action.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def notify_order_schedule_action(action_id: int) -> None:
    action = db.session.get(OrderEventAction, action_id)
    if action is None:
        return
    if action.status in {OrderEventAction.STATUS_SUCCESS, OrderEventAction.STATUS_SKIPPED}:
        return
    if action.scheduled_for is not None and action.scheduled_for > datetime.now(timezone.utc):
        return

    action.attempts = (action.attempts or 0) + 1
    db.session.commit()

    try:
        if action.event is None or action.event.order is None:
            _mark_action_failed(action, "Order event context is missing")
            return

        payload = action.payload if isinstance(action.payload, dict) else {}
        target_id = payload.get("target_id")
        scheduled_date = payload.get("scheduled_date")

        if type(target_id) is not int:
            _mark_action_failed(action, "Schedule notification target_id is missing")
            return
        if not isinstance(scheduled_date, str) or not scheduled_date.strip():
            _mark_action_failed(action, "Schedule notification scheduled_date is missing")
            return

        result = notify_order_schedule(target_id, action.event.order.id, scheduled_date.strip())
        status = (result or {}).get("status")
        reason = (result or {}).get("reason")

        if status == "skipped":
            _mark_action_skipped(action, reason or "Schedule notification was skipped")
            return

        _mark_action_success(action)
    except Exception as exc:
        _mark_action_failed(action, str(exc))
