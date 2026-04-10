from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
    build_stop_time_warnings,
)


def _route_solution(plan_start: datetime | None = None, plan_end: datetime | None = None):
    delivery_plan = SimpleNamespace(start_date=plan_start, end_date=plan_end)
    local_delivery_plan = SimpleNamespace(delivery_plan=delivery_plan)
    return SimpleNamespace(local_delivery_plan=local_delivery_plan)


def test_delivery_windows_are_authoritative_over_legacy_fields():
    order = SimpleNamespace(
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    route_solution = _route_solution(
        datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 3, 23, 59, 59, tzinfo=timezone.utc),
    )
    arrival = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    warnings = build_stop_time_warnings(order, arrival, route_solution)

    assert warnings
    assert warnings[0]["type"] == "time_window_violation"


def test_time_windows_use_half_open_interval_end_exclusive():
    order = SimpleNamespace(
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    route_solution = _route_solution()

    at_start = build_stop_time_warnings(
        order,
        datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
        route_solution,
    )
    at_end = build_stop_time_warnings(
        order,
        datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
        route_solution,
    )

    assert at_start == []
    assert at_end
    assert at_end[0]["type"] == "time_window_violation"


def test_apply_evaluation_keeps_non_time_warnings():
    order = SimpleNamespace(
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 2, 11, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    route_solution = _route_solution()
    stop = SimpleNamespace(
        expected_arrival_time=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
        has_constraint_violation=True,
        constraint_warnings=[{"type": "capacity_exceeded", "severity": "error"}],
        reason_was_skipped="Capacity issue",
    )

    changed = apply_stop_time_window_evaluation(
        stop=stop,
        order=order,
        route_solution=route_solution,
        arrival_time=stop.expected_arrival_time,
    )

    assert changed is False
    assert stop.has_constraint_violation is True
    assert stop.constraint_warnings == [{"type": "capacity_exceeded", "severity": "error"}]
