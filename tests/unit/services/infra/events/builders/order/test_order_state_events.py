from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.domain.order.order_states import OrderState
from Delivery_app_BK.services.infra.events.builders.order import (
    build_order_state_lifecycle_event,
    build_order_state_transition_events,
    build_order_status_changed_event,
)


def test_build_order_status_changed_event_payload():
    order = SimpleNamespace(id=13, team_id=7)
    state = SimpleNamespace(id=4, name=OrderState.READY.value)

    event = build_order_status_changed_event(
        order_instance=order,
        old_state_id=2,
        state_instance=state,
    )

    assert event["event_name"] == OrderEvent.STATUS_CHANGED.value
    assert event["payload"]["old_order_state_id"] == 2
    assert event["payload"]["new_order_state_id"] == 4
    assert event["payload"]["new_order_state_name"] == OrderState.READY.value


def test_build_order_state_lifecycle_event_maps_known_state():
    order = SimpleNamespace(id=13, team_id=7)
    state = SimpleNamespace(id=2, name=OrderState.CONFIRMED.value)

    event = build_order_state_lifecycle_event(order, state)
    assert event["event_name"] == OrderEvent.CONFIRMED.value


def test_build_order_state_lifecycle_event_maps_unknown_to_fail():
    order = SimpleNamespace(id=13, team_id=7)
    state = SimpleNamespace(id=99, name="CustomState")

    event = build_order_state_lifecycle_event(order, state)
    assert event["event_name"] == OrderEvent.FAIL.value


def test_build_order_state_transition_events_returns_both_events_for_changed_state():
    order = SimpleNamespace(id=13, team_id=7)
    state = SimpleNamespace(id=8, name=OrderState.CANCELLED.value)

    events = build_order_state_transition_events(
        order_instance=order,
        old_state_id=2,
        state_instance=state,
    )
    assert len(events) == 2
    assert events[0]["event_name"] == OrderEvent.STATUS_CHANGED.value
    assert events[1]["event_name"] == OrderEvent.CANCELLED.value
