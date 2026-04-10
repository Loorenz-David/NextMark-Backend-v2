from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.infra.events.builders.order import (
    build_route_plan_changed_event,
    build_delivery_window_rescheduled_by_user_event,
)


def test_build_delivery_window_rescheduled_by_user_event_formats_payload():
    order = SimpleNamespace(id=7, team_id=3)
    old_earliest = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    old_latest = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    new_earliest = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    new_latest = datetime(2026, 3, 1, 13, 0, tzinfo=timezone.utc)

    event = build_delivery_window_rescheduled_by_user_event(
        order_instance=order,
        old_earliest=old_earliest,
        old_latest=old_latest,
        new_earliest=new_earliest,
        new_latest=new_latest,
    )

    assert event["order_id"] == 7
    assert event["team_id"] == 3
    assert event["event_name"] == OrderEvent.DELIVERY_WINDOW_RESCHEDULED_BY_USER.value
    assert event["payload"]["old_window_start"] == old_earliest.isoformat()
    assert event["payload"]["old_window_end"] == old_latest.isoformat()
    assert event["payload"]["new_window_start"] == new_earliest.isoformat()
    assert event["payload"]["new_window_end"] == new_latest.isoformat()


def test_build_route_plan_changed_event_uses_date_strategy_field():
    order = SimpleNamespace(id=12, team_id=5)
    new_plan = SimpleNamespace(id=99, date_strategy="single")

    event = build_route_plan_changed_event(
        order_instance=order,
        old_plan_id=41,
        new_plan=new_plan,
    )

    assert event["event_name"] == OrderEvent.DELIVERY_PLAN_CHANGED.value
    assert event["payload"]["old_route_plan_id"] == 41
    assert event["payload"]["new_route_plan_id"] == 99
    assert event["payload"]["new_plan_type"] == "single"
    assert event["payload"]["new_date_strategy"] == "single"
