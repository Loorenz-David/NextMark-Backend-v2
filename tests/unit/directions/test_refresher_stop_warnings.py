from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.directions.domain.models import (
    DirectionsRequest,
    DirectionsRequestBuildResult,
    DirectionsResult,
    DirectionsStopResult,
)
from Delivery_app_BK.directions.services.refresher import (
    _build_stop_warnings,
    apply_directions_result,
)


def _make_route_solution(plan_start: datetime | None, plan_end: datetime | None):
    delivery_plan = SimpleNamespace(start_date=plan_start, end_date=plan_end)
    local_delivery_plan = SimpleNamespace(delivery_plan=delivery_plan)
    return SimpleNamespace(
        local_delivery_plan=local_delivery_plan,
        set_end_time=None,
        route_warnings=None,
        has_route_warnings=False,
        expected_start_time=None,
        expected_end_time=None,
        total_distance_meters=None,
        total_travel_time_seconds=None,
        start_leg_polyline=None,
        end_leg_polyline=None,
        stops=[],
    )


def _make_order(
    delivery_windows=None,
):
    return SimpleNamespace(
        delivery_windows=list(delivery_windows or []),
    )


def test_plan_window_fallback_creates_violation_when_order_windows_missing():
    route_solution = _make_route_solution(
        datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
    )
    order = _make_order()
    arrival = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)

    warnings = _build_stop_warnings(order, arrival, route_solution)

    assert warnings
    assert warnings[0]["type"] == "time_window_violation"


def test_plan_window_fallback_allows_arrival_inside_window():
    route_solution = _make_route_solution(
        datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
    )
    order = _make_order()
    arrival = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

    warnings = _build_stop_warnings(order, arrival, route_solution)

    assert warnings == []


def test_explicit_order_windows_take_precedence_over_plan_window():
    route_solution = _make_route_solution(
        datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
    )
    order = _make_order(
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    arrival = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    warnings = _build_stop_warnings(order, arrival, route_solution)

    assert warnings
    assert warnings[0]["type"] == "time_window_violation"


def test_apply_directions_result_uses_stop_order_relationship_when_order_map_missing():
    order = _make_order()
    order.id = 100

    stop = SimpleNamespace(
        id=10,
        order_id=100,
        stop_order=1,
        expected_arrival_time=None,
        eta_status="stale",
        in_range=False,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        to_next_polyline=None,
        order=order,
    )

    route_solution = _make_route_solution(
        datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
    )
    route_solution.stops = [stop]

    directions_result = DirectionsResult(
        total_distance_meters=100,
        total_duration_seconds=100,
        leg_polylines=["a", "b"],
        start_time=datetime(2026, 2, 28, 8, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc),
        stop_results=[
            DirectionsStopResult(
                order_id=100,
                arrival_time=datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc),
                travel_duration_seconds=100,
                distance_meters=100,
            )
        ],
    )

    build_result = DirectionsRequestBuildResult(
        request=DirectionsRequest(
            origin={"latitude": 1.0, "longitude": 1.0},
            destination={"latitude": 2.0, "longitude": 2.0},
            intermediates=[],
            travel_mode="DRIVING",
            consider_traffic=True,
            route_modifiers={},
            departure_time=datetime(2026, 2, 28, 8, 0, 0, tzinfo=timezone.utc),
        ),
        full_recompute=True,
        effective_start_position=1,
        anchor_order_id=None,
        affected_order_ids=[100],
    )

    changed_stops = apply_directions_result(
        route_solution=route_solution,
        directions_result=directions_result,
        orders_by_id={},
        build_result=build_result,
    )

    assert changed_stops
    assert stop.has_constraint_violation is True
    assert stop.constraint_warnings
    assert stop.constraint_warnings[0]["type"] == "time_window_violation"
