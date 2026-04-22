from datetime import datetime, timezone

from Delivery_app_BK.models import db, OrderEventAction, OrderEvent
from Delivery_app_BK.services.infra.events.action_dispatch import enqueue_order_action
from Delivery_app_BK.services.infra.events.realtime_refresh import notify_order_event_history_changed
from Delivery_app_BK.services.infra.messaging.action_scheduling import resolve_order_action_schedule


def _upsert_action(
    order_event_id: int,
    action_name: str,
    team_id: int | None,
    *,
    action_scope: str = "",
    payload: dict | None = None,
    resolved_schedule,
) -> OrderEventAction:
    action = (
        db.session.query(OrderEventAction)
        .filter(
            OrderEventAction.event_id == order_event_id,
            OrderEventAction.action_name == action_name,
            OrderEventAction.action_scope == action_scope,
        )
        .first()
    )

    if resolved_schedule is None:
        status = OrderEventAction.STATUS_PENDING
        last_error = None
        scheduled_for = None
        schedule_anchor_type = None
        schedule_anchor_at = None
        processed_at = None
    else:
        status = (
            OrderEventAction.STATUS_SKIPPED
            if resolved_schedule.skip_reason
            else OrderEventAction.STATUS_PENDING
        )
        last_error = resolved_schedule.skip_reason
        scheduled_for = resolved_schedule.scheduled_for
        schedule_anchor_type = resolved_schedule.schedule_anchor_type
        schedule_anchor_at = resolved_schedule.schedule_anchor_at
        processed_at = datetime.now(timezone.utc) if resolved_schedule.skip_reason else None

    if action is None:
        action = OrderEventAction(
            event_id=order_event_id,
            action_name=action_name,
            action_scope=action_scope,
            payload=payload,
            team_id=team_id,
            status=status,
            attempts=0,
            last_error=last_error,
            scheduled_for=scheduled_for,
            schedule_anchor_type=schedule_anchor_type,
            schedule_anchor_at=schedule_anchor_at,
            processed_at=processed_at,
        )
        db.session.add(action)
        db.session.flush()
        return action

    action.status = status
    action.payload = payload
    action.last_error = last_error
    action.scheduled_for = scheduled_for
    action.schedule_anchor_type = schedule_anchor_type
    action.schedule_anchor_at = schedule_anchor_at
    action.processed_at = processed_at
    action.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return action


def run_action(order_event, action_name: str, _runner) -> None:
    team_id = getattr(order_event, "team_id", None)
    resolved_schedule = resolve_order_action_schedule(order_event, action_name)
    if resolved_schedule is None:
        return

    action = _upsert_action(
        order_event.id,
        action_name,
        team_id,
        resolved_schedule=resolved_schedule,
    )
    db.session.commit()
    notify_order_event_history_changed(order_event.id)
    if action.status == OrderEventAction.STATUS_SKIPPED:
        return

    try:
        enqueue_order_action(action)
    except Exception as exc:
        failed_action = db.session.get(OrderEventAction, action.id)
        if failed_action is None:
            return
        failed_action.attempts = (failed_action.attempts or 0) + 1
        failed_action.status = OrderEventAction.STATUS_FAILED
        failed_action.last_error = str(exc)
        db.session.commit()
        notify_order_event_history_changed(failed_action.event_id)


def run_immediate_action(
    order_event,
    action_name: str,
    _runner,
    *,
    action_scope: str = "",
    payload: dict | None = None,
) -> None:
    team_id = getattr(order_event, "team_id", None)
    action = _upsert_action(
        order_event.id,
        action_name,
        team_id,
        action_scope=action_scope,
        payload=payload,
        resolved_schedule=None,
    )
    db.session.commit()
    notify_order_event_history_changed(order_event.id)

    try:
        enqueue_order_action(action)
    except Exception as exc:
        failed_action = db.session.get(OrderEventAction, action.id)
        if failed_action is None:
            return
        failed_action.attempts = (failed_action.attempts or 0) + 1
        failed_action.status = OrderEventAction.STATUS_FAILED
        failed_action.last_error = str(exc)
        db.session.commit()
        notify_order_event_history_changed(failed_action.event_id)
