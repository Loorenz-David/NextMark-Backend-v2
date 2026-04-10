from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.directions.domain.models import DirectionsResult, DirectionsStopResult
from Delivery_app_BK.directions.services.refresher import apply_directions_result
from Delivery_app_BK.directions.services.request_builder import build_directions_request_bundle
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP


def _make_order(order_id: int, lat: float, lng: float):
    return SimpleNamespace(
        id=order_id,
        client_address={
            "street_address": f"{order_id} Main St",
            "coordinates": {"lat": lat, "lng": lng},
        },
        items=[],
        delivery_windows=[],
    )


def _make_stop(stop_id: int, order_id: int, stop_order: int, minutes: int):
    return SimpleNamespace(
        id=stop_id,
        order_id=order_id,
        stop_order=stop_order,
        service_time={"time": minutes, "per_item": 0},
        service_duration=None,
        expected_arrival_time=None,
        eta_status="stale",
        in_range=False,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        to_next_polyline=None,
        order=None,
    )


def _make_route_solution(stops):
    route_plan = SimpleNamespace(
        start_date=datetime(2026, 3, 7, 8, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 7, 23, 59, 59, tzinfo=timezone.utc),
    )
    route_group = SimpleNamespace(route_plan=route_plan)
    return SimpleNamespace(
        id=1,
        stops=stops,
        start_location={"coordinates": {"lat": 57.7, "lng": 11.97}},
        end_location=None,
        route_end_strategy=ROUND_TRIP,
        stops_service_time=None,
        set_start_time=None,
        set_end_time=None,
        route_group=route_group,
        route_warnings=None,
        has_route_warnings=False,
        expected_start_time=None,
        expected_end_time=None,
        total_distance_meters=None,
        total_travel_time_seconds=None,
        start_leg_polyline=None,
        end_leg_polyline=None,
    )


def test_build_directions_request_bundle_collapses_contiguous_same_coordinate_stops():
    order_1 = _make_order(101, 57.700001, 11.970001)
    order_2 = _make_order(102, 57.7000012, 11.9700011)
    order_3 = _make_order(103, 57.71, 11.98)
    orders_by_id = {
        order_1.id: order_1,
        order_2.id: order_2,
        order_3.id: order_3,
    }
    stops = [
        _make_stop(1, 101, 1, 10),
        _make_stop(2, 102, 2, 5),
        _make_stop(3, 103, 3, 7),
    ]
    route_solution = _make_route_solution(stops)

    build_result = build_directions_request_bundle(
        route_solution=route_solution,
        orders_by_id=orders_by_id,
        recompute_from_position=1,
    )

    assert len(build_result.request.intermediates) == 2
    assert build_result.request.intermediates[0].service_duration_seconds == 15 * 60
    assert len(build_result.visit_groups) == 2
    assert [member.order_id for member in build_result.visit_groups[0].members] == [101, 102]
    assert [member.order_id for member in build_result.visit_groups[1].members] == [103]


def test_apply_directions_result_expands_grouped_visit_arrivals_and_polylines():
    order_1 = _make_order(101, 57.700001, 11.970001)
    order_2 = _make_order(102, 57.7000011, 11.9700012)
    order_3 = _make_order(103, 57.71, 11.98)
    orders_by_id = {
        order_1.id: order_1,
        order_2.id: order_2,
        order_3.id: order_3,
    }
    stop_1 = _make_stop(1, 101, 1, 10)
    stop_2 = _make_stop(2, 102, 2, 5)
    stop_3 = _make_stop(3, 103, 3, 7)
    stop_1.order = order_1
    stop_2.order = order_2
    stop_3.order = order_3

    route_solution = _make_route_solution([stop_1, stop_2, stop_3])
    build_result = build_directions_request_bundle(
        route_solution=route_solution,
        orders_by_id=orders_by_id,
        recompute_from_position=1,
    )

    changed_stops = apply_directions_result(
        route_solution=route_solution,
        directions_result=DirectionsResult(
            total_distance_meters=1500,
            total_duration_seconds=2400,
            leg_polylines=["start-leg", "between-groups", "end-leg"],
            start_time=datetime(2026, 3, 7, 8, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 7, 8, 52, 0, tzinfo=timezone.utc),
            stop_results=[
                DirectionsStopResult(
                    order_id=101,
                    arrival_time=datetime(2026, 3, 7, 8, 20, 0, tzinfo=timezone.utc),
                    travel_duration_seconds=1200,
                    distance_meters=800,
                ),
                DirectionsStopResult(
                    order_id=103,
                    arrival_time=datetime(2026, 3, 7, 8, 40, 0, tzinfo=timezone.utc),
                    travel_duration_seconds=900,
                    distance_meters=700,
                ),
            ],
        ),
        orders_by_id=orders_by_id,
        build_result=build_result,
    )

    assert [stop.id for stop in changed_stops] == [1, 2, 3]
    assert stop_1.expected_arrival_time == datetime(2026, 3, 7, 8, 20, 0, tzinfo=timezone.utc)
    assert stop_2.expected_arrival_time == datetime(2026, 3, 7, 8, 30, 0, tzinfo=timezone.utc)
    assert stop_3.expected_arrival_time == datetime(2026, 3, 7, 8, 40, 0, tzinfo=timezone.utc)
    assert route_solution.start_leg_polyline == "start-leg"
    assert stop_1.to_next_polyline is None
    assert stop_2.to_next_polyline == "between-groups"
    assert stop_3.to_next_polyline is None
    assert route_solution.end_leg_polyline == "end-leg"


def test_build_directions_request_bundle_treats_set_start_time_as_team_local_wall_clock():
    order = _make_order(101, 57.700001, 11.970001)
    orders_by_id = {order.id: order}
    stop = _make_stop(1, 101, 1, 10)
    route_solution = _make_route_solution([stop])
    route_solution.set_start_time = "17:00"

    build_result = build_directions_request_bundle(
        route_solution=route_solution,
        orders_by_id=orders_by_id,
        time_zone="Europe/Stockholm",
        recompute_from_position=1,
    )

    assert build_result.request.departure_time == datetime(
        2026, 3, 7, 16, 0, 0, tzinfo=timezone.utc
    )
