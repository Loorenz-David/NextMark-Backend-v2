from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.route_optimization.constants.is_optimized import IS_OPTIMIZED_OPTIMIZE
from Delivery_app_BK.services.commands.delivery_plan.local_delivery.route_solution.update_route_solution_from_plan import (
    update_route_solution_from_plan,
)


def _build_route_solution(*, set_start_time: str | None, arrival: datetime):
    stop = SimpleNamespace(
        id=1,
        stop_order=1,
        expected_arrival_time=arrival,
        eta_status="valid",
        constraint_warnings=None,
        has_constraint_violation=False,
        reason_was_skipped=None,
    )

    return SimpleNamespace(
        id=100,
        is_optimized=IS_OPTIMIZED_OPTIMIZE,
        set_start_time=set_start_time,
        set_end_time=None,
        eta_tolerance_seconds=None,
        stops_service_time=None,
        expected_start_time=datetime(2026, 2, 28, 7, 0, 0, tzinfo=timezone.utc),
        expected_end_time=datetime(2026, 2, 28, 19, 0, 0, tzinfo=timezone.utc),
        start_location={"coordinates": {"lat": 1.0, "lng": 1.0}},
        end_location={"coordinates": {"lat": 2.0, "lng": 2.0}},
        route_end_strategy="round_trip",
        stops=[stop],
        local_delivery_plan=None,
        driver_id=None,
        route_warnings=None,
        has_route_warnings=False,
    )


def test_time_text_change_rebuilds_stop_warnings_when_window_equivalent():
    plan_start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    plan_end = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
    # Outside the effective start window (09:00)
    arrival = datetime(2026, 2, 28, 8, 0, 0, tzinfo=timezone.utc)

    route_solution = _build_route_solution(set_start_time="9:00", arrival=arrival)

    updated, stops_changed, original = update_route_solution_from_plan(
        route_solution=route_solution,
        updates={"set_start_time": "09:00:00"},
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=plan_start,
        previous_plan_end=plan_end,
        create_variant_on_save=False,
        time_zone="UTC",
    )

    assert original is None
    assert updated is route_solution
    assert stops_changed is True
    assert updated.stops[0].has_constraint_violation is True
    assert updated.stops[0].constraint_warnings
    assert updated.stops[0].constraint_warnings[0]["type"] == "time_window_violation"


def test_set_start_updates_expected_start_and_shifts_expected_end():
    plan_start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    plan_end = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
    arrival = datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc)

    route_solution = _build_route_solution(set_start_time="08:00:00", arrival=arrival)
    route_solution.set_end_time = "18:00:00"

    updated, _, _ = update_route_solution_from_plan(
        route_solution=route_solution,
        updates={
            "set_start_time": "09:00:00",
            "set_end_time": "17:30:00",
        },
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=plan_start,
        previous_plan_end=plan_end,
        create_variant_on_save=False,
        time_zone="UTC",
    )

    assert updated.expected_start_time == datetime(
        2026, 2, 28, 9, 0, 0, tzinfo=timezone.utc
    )
    assert updated.expected_end_time == datetime(
        2026, 2, 28, 20, 0, 0, tzinfo=timezone.utc
    )
    assert updated.has_route_warnings is True
    assert updated.route_warnings
    assert updated.route_warnings[0]["type"] == "route_end_time_exceeded"


def test_plan_window_change_updates_expected_start_and_shifts_expected_end():
    previous_plan_start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    previous_plan_end = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
    plan_start = datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc)
    plan_end = datetime(2026, 3, 2, 23, 59, 59, tzinfo=timezone.utc)
    arrival = datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc)

    route_solution = _build_route_solution(set_start_time=None, arrival=arrival)

    updated, _, _ = update_route_solution_from_plan(
        route_solution=route_solution,
        updates={},
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=previous_plan_start,
        previous_plan_end=previous_plan_end,
        create_variant_on_save=False,
        time_zone="UTC",
    )

    assert updated.expected_start_time == plan_start
    assert updated.expected_end_time == datetime(
        2026, 3, 2, 19, 0, 0, tzinfo=timezone.utc
    )
    assert updated.has_route_warnings is False
    assert updated.route_warnings is None


def test_set_end_change_can_clear_route_end_time_exceeded_warning():
    plan_start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    plan_end = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
    arrival = datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc)

    route_solution = _build_route_solution(set_start_time="08:00:00", arrival=arrival)
    route_solution.set_end_time = "18:00:00"
    route_solution.route_warnings = [
        {
            "type": "route_end_time_exceeded",
            "severity": "error",
            "message": "Route ends after allowed end time",
            "route_expected_end": datetime(
                2026, 2, 28, 19, 0, 0, tzinfo=timezone.utc
            ).isoformat(),
            "route_allowed_end": datetime(
                2026, 2, 28, 18, 0, 0, tzinfo=timezone.utc
            ).isoformat(),
        }
    ]
    route_solution.has_route_warnings = True

    updated, _, _ = update_route_solution_from_plan(
        route_solution=route_solution,
        updates={"set_end_time": "20:00:00"},
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=plan_start,
        previous_plan_end=plan_end,
        create_variant_on_save=False,
        time_zone="UTC",
    )

    assert updated.expected_end_time == datetime(
        2026, 2, 28, 19, 0, 0, tzinfo=timezone.utc
    )
    assert updated.has_route_warnings is False
    assert updated.route_warnings is None


def test_set_start_updates_expected_times_and_rechecks_violations_when_moved_backward():
    plan_start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    plan_end = datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
    arrival = datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc)

    route_solution = _build_route_solution(set_start_time="10:00:00", arrival=arrival)
    route_solution.expected_end_time = datetime(2026, 2, 28, 20, 0, 0, tzinfo=timezone.utc)
    route_solution.stops[0].order = SimpleNamespace(
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 2, 28, 9, 30, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 2, 28, 10, 30, 0, tzinfo=timezone.utc),
            )
        ],
    )

    updated, stops_changed, _ = update_route_solution_from_plan(
        route_solution=route_solution,
        updates={"set_start_time": "09:00:00"},
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=plan_start,
        previous_plan_end=plan_end,
        create_variant_on_save=False,
        time_zone="UTC",
    )

    assert stops_changed is True
    assert updated.expected_start_time == datetime(
        2026, 2, 28, 9, 0, 0, tzinfo=timezone.utc
    )
    assert updated.expected_end_time == datetime(
        2026, 2, 28, 19, 0, 0, tzinfo=timezone.utc
    )
    assert updated.stops[0].expected_arrival_time == datetime(
        2026, 2, 28, 9, 0, 0, tzinfo=timezone.utc
    )
    assert updated.stops[0].has_constraint_violation is True
    assert updated.stops[0].constraint_warnings
    assert updated.stops[0].constraint_warnings[0]["type"] == "time_window_violation"
