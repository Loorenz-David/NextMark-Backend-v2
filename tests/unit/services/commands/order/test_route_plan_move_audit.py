import importlib
from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.order_events import OrderEvent

module = importlib.import_module("Delivery_app_BK.services.commands.order.update_order_route_plan")


def test_plan_move_changes_are_recorded_on_the_plan_change_event(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        module,
        "record_order_audit_changes",
        lambda _ctx, **kwargs: recorded.append(kwargs),
    )
    plan_changed = {
        "order_id": 1,
        "team_id": 7,
        "event_name": OrderEvent.DELIVERY_PLAN_CHANGED.value,
        "payload": {"old_route_plan_id": None, "new_route_plan_id": 6},
    }
    rescheduled = {
        "order_id": 1,
        "team_id": 7,
        "event_name": OrderEvent.DELIVERY_RESCHEDULED.value,
        "payload": {"new_plan_start": "2026-10-19T00:00:00+00:00", "new_plan_end": "2026-10-19T23:59:59+00:00"},
    }

    module._finalize_plan_move_events(SimpleNamespace(user_id=2), [plan_changed, rescheduled], None)

    assert len(recorded) == 1
    assert recorded[0]["event_id"] == plan_changed["event_id"]
    assert [change.field_name for change in recorded[0]["changes"]] == [
        "route_plan_id",
        "delivery_dates",
    ]
    assert rescheduled["payload"]["notification_folded_into"] == plan_changed["event_id"]
