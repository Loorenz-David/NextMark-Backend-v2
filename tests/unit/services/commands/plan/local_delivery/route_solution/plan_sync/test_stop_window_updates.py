from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync.stop_window_updates import (
    apply_time_window_update,
)


def test_shift_times_applies_negative_delta_when_window_moves_earlier():
    old_window = (
        datetime(2026, 3, 5, 9, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 5, 23, 59, 59, tzinfo=timezone.utc),
    )
    new_window = (
        datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 3, 23, 59, 59, tzinfo=timezone.utc),
    )

    stop = SimpleNamespace(
        expected_arrival_time=datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc),
        eta_status="valid",
        constraint_warnings=None,
        has_constraint_violation=False,
        reason_was_skipped=None,
    )
    route_solution = SimpleNamespace(stops=[stop])

    has_updates, has_violation = apply_time_window_update(
        route_solution=route_solution,
        old_window=old_window,
        new_window=new_window,
        shift_times=True,
    )

    assert has_updates is True
    assert has_violation is False
    assert stop.expected_arrival_time == datetime(2026, 3, 3, 12, 0, 0, tzinfo=timezone.utc)
    assert stop.has_constraint_violation is False
