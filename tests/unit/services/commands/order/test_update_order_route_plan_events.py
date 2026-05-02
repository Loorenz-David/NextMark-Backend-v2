from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.order import update_order_route_plan as module


def test_route_plan_move_reschedule_reason_for_unplanned_order_assignment():
    new_plan = SimpleNamespace(
        start_date=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 2, 18, 0, tzinfo=timezone.utc),
    )

    assert module._route_plan_move_reschedule_reason(
        old_plan_id=None,
        old_plan=None,
        new_plan=new_plan,
    ) == "plan_assigned"


def test_route_plan_move_reschedule_reason_for_plan_date_change():
    old_plan = SimpleNamespace(
        start_date=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc),
    )
    new_plan = SimpleNamespace(
        start_date=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 2, 18, 0, tzinfo=timezone.utc),
    )

    assert module._route_plan_move_reschedule_reason(
        old_plan_id=10,
        old_plan=old_plan,
        new_plan=new_plan,
    ) == "plan_move_date_changed"


def test_route_plan_move_reschedule_reason_skips_same_window_plan_move():
    old_plan = SimpleNamespace(
        start_date=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 2, 18, 0, tzinfo=timezone.utc),
    )
    new_plan = SimpleNamespace(
        start_date=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 2, 18, 0, tzinfo=timezone.utc),
    )

    assert module._route_plan_move_reschedule_reason(
        old_plan_id=10,
        old_plan=old_plan,
        new_plan=new_plan,
    ) is None
