from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import (
    AppEventOutbox,
    OrderEvent,
    OrderEventAction,
    RoutePlanEvent,
    RoutePlanEventAction,
    db,
)
from Delivery_app_BK.services.infra.events.action_dispatch import (
    enqueue_route_plan_action,
    enqueue_order_action,
)


def replay_order_event(event_row_id: int) -> bool:
    return _requeue_event(db.session.get(OrderEvent, event_row_id))


def replay_route_plan_event(event_row_id: int) -> bool:
    return _requeue_event(db.session.get(RoutePlanEvent, event_row_id))


def replay_app_event(event_row_id: int) -> bool:
    return _requeue_event(db.session.get(AppEventOutbox, event_row_id))


def requeue_order_action(action_id: int) -> bool:
    action = db.session.get(OrderEventAction, action_id)
    if action is None:
        return False
    action.status = OrderEventAction.STATUS_PENDING
    action.last_error = None
    action.processed_at = None
    action.enqueued_at = None
    db.session.commit()
    enqueue_order_action(action)
    return True


def requeue_route_plan_action(action_id: int) -> bool:
    action = db.session.get(RoutePlanEventAction, action_id)
    if action is None:
        return False
    action.status = RoutePlanEventAction.STATUS_PENDING
    action.last_error = None
    action.processed_at = None
    action.enqueued_at = None
    db.session.commit()
    enqueue_route_plan_action(action)
    return True


def _requeue_event(event_row) -> bool:
    if event_row is None:
        return False

    event_row.dispatch_status = event_row.DISPATCH_STATUS_PENDING
    event_row.claimed_at = None
    event_row.claimed_by = None
    event_row.last_error = None
    event_row.next_attempt_at = datetime.now(timezone.utc)
    db.session.commit()
    return True
