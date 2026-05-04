from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_OPTIMIZE,
    IS_OPTIMIZED_PARTIAL,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.clone import (
    clone_route_solution,
)


def _address(lat: float, lng: float):
    return {
        "street_address": "Borgagatan 10",
        "postal_code": "164 75",
        "city": "Kista",
        "country": "Sweden",
        "coordinates": {"lat": lat, "lng": lng},
    }


def _make_route_solution():
    stop = SimpleNamespace(
        id=10,
        order_id=100,
        service_duration=None,
        service_time={"time": 180, "per_item": 120},
        in_range=True,
        stop_order=1,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        eta_status="valid",
        expected_arrival_time=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
        expected_service_duration_seconds=300,
        expected_departure_time=datetime(2026, 5, 4, 12, 5, 0, tzinfo=timezone.utc),
        actual_arrival_time=None,
        actual_departure_time=None,
        to_next_polyline="encoded-polyline",
        team_id=7,
    )
    route_group = SimpleNamespace(route_solutions=[])
    route_solution = SimpleNamespace(
        id=1,
        route_group=route_group,
        version=1,
        algorithm="google_route_optimization",
        score=123.0,
        total_distance_meters=1000,
        total_travel_time_seconds=200,
        expected_start_time=datetime(2026, 5, 4, 11, 0, 0, tzinfo=timezone.utc),
        expected_end_time=datetime(2026, 5, 4, 13, 0, 0, tzinfo=timezone.utc),
        actual_start_time=None,
        actual_end_time=None,
        has_route_warnings=False,
        route_warnings=None,
        start_location=_address(1.0, 2.0),
        end_location=_address(1.0, 2.0),
        set_start_time="11:00",
        set_end_time="15:00",
        eta_tolerance_seconds=0,
        eta_message_tolerance=1200,
        stops_service_time={"time": 180, "per_item": 120},
        is_selected=True,
        is_optimized=IS_OPTIMIZED_OPTIMIZE,
        driver_id=3,
        vehicle_id=99,
        route_group_id=5,
        team_id=7,
        start_leg_polyline="start-polyline",
        end_leg_polyline="end-polyline",
        stops=[stop],
    )
    route_group.route_solutions.append(route_solution)
    return route_solution


def test_clone_route_solution_preserves_vehicle_assignment():
    route_solution = _make_route_solution()

    cloned, stop_map, original = clone_route_solution(route_solution)

    assert cloned.vehicle_id == 99
    assert cloned.driver_id == 3
    assert cloned.is_selected is True
    assert cloned.is_optimized == IS_OPTIMIZED_PARTIAL
    assert original is route_solution
    assert original.is_selected is False
    assert original.is_optimized == IS_OPTIMIZED_PARTIAL
    assert stop_map[10].order_id == 100
