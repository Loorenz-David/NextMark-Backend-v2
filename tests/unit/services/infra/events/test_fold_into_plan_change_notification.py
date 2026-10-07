from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.infra.events.builders.order import (
    fold_into_plan_change_notification,
)


def _event(order_id, event_name, payload=None):
    return {"order_id": order_id, "team_id": 7, "event_name": event_name, "payload": payload or {}}


def test_scheduling_events_point_at_the_plan_change_which_carries_the_status():
    plan_changed = _event(1, OrderEvent.DELIVERY_PLAN_CHANGED.value, {"new_route_plan_id": 5})
    rescheduled = _event(1, OrderEvent.DELIVERY_RESCHEDULED.value, {"reason": "plan_assigned"})
    status_changed = _event(
        1,
        OrderEvent.STATUS_CHANGED.value,
        {"old_order_state_id": 1, "new_order_state_id": 2},
    )
    confirmed = _event(1, OrderEvent.CONFIRMED.value)

    events = fold_into_plan_change_notification(
        [plan_changed, rescheduled, status_changed, confirmed]
    )

    lead_id = plan_changed["event_id"]
    assert lead_id
    assert "notification_folded_into" not in plan_changed["payload"]
    assert all(
        event["payload"]["notification_folded_into"] == lead_id
        for event in (rescheduled, status_changed, confirmed)
    )
    assert plan_changed["payload"]["notification_old_order_state_id"] == 1
    assert plan_changed["payload"]["notification_new_order_state_id"] == 2
    # Nothing is dropped: every event still reaches the history.
    assert len(events) == 4


def test_events_of_orders_without_a_plan_change_are_left_alone():
    other = _event(2, OrderEvent.STATUS_CHANGED.value, {"old_order_state_id": 1})

    fold_into_plan_change_notification(
        [_event(1, OrderEvent.DELIVERY_PLAN_CHANGED.value), other]
    )

    assert "notification_folded_into" not in other["payload"]
    assert "event_id" not in other


def test_the_plan_change_carries_the_reschedule_dates():
    plan_changed = _event(1, OrderEvent.DELIVERY_PLAN_CHANGED.value)
    rescheduled = _event(
        1,
        OrderEvent.DELIVERY_RESCHEDULED.value,
        {
            "old_plan_start": "2026-10-17T00:00:00+00:00",
            "old_plan_end": "2026-10-17T23:59:59+00:00",
            "new_plan_start": "2026-10-19T00:00:00+00:00",
            "new_plan_end": "2026-10-19T23:59:59+00:00",
        },
    )

    fold_into_plan_change_notification([plan_changed, rescheduled])

    assert plan_changed["payload"]["notification_old_plan_start"] == "2026-10-17T00:00:00+00:00"
    assert plan_changed["payload"]["notification_new_plan_end"] == "2026-10-19T23:59:59+00:00"
