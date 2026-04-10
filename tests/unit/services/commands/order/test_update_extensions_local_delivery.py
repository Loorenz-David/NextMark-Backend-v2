from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.order.update_extensions.local_delivery import (
    handle_local_delivery_order_update_extension,
)
from Delivery_app_BK.services.commands.order.update_extensions.types import (
    OrderUpdateChangeFlags,
    OrderUpdateDelta,
    OrderUpdateExtensionContext,
)


def _make_route_solution(route_plan, stops):
    route_group = SimpleNamespace(route_plan=route_plan, route_plan_id=route_plan.id)
    return SimpleNamespace(
        id=10,
        client_id="rs_10",
        label="route",
        version=1,
        algorithm=None,
        score=None,
        total_distance_meters=1000,
        total_travel_time_seconds=1800,
        start_leg_polyline=None,
        end_leg_polyline=None,
        route_warnings=None,
        has_route_warnings=False,
        start_location=None,
        end_location=None,
        expected_start_time=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        expected_end_time=datetime(2026, 3, 31, 13, 35, 0, tzinfo=timezone.utc),
        actual_start_time=None,
        actual_end_time=None,
        set_start_time=None,
        set_end_time=None,
        eta_tolerance_seconds=0,
        stops_service_time=None,
        is_selected=True,
        is_optimized="partial optimize",
        driver_id=None,
        driver=None,
        vehicle_id=None,
        route_end_strategy="round_trip",
        route_group=route_group,
        route_group_id=route_group.route_plan_id,
        created_at=None,
        updated_at=None,
        stops=stops,
    )


def _make_stop(stop_id, order_id, stop_order, arrival, departure):
    return SimpleNamespace(
        id=stop_id,
        client_id=f"stop_{stop_id}",
        route_solution_id=10,
        order_id=order_id,
        service_duration=None,
        service_time=None,
        in_range=True,
        stop_order=stop_order,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        eta_status="estimated",
        expected_arrival_time=arrival,
        expected_departure_time=departure,
        expected_service_duration_seconds=int((departure - arrival).total_seconds()),
        actual_arrival_time=None,
        actual_departure_time=None,
        to_next_polyline=None,
        order=None,
    )


def test_window_update_clamps_changed_stop_and_shifts_downstream_suffix():
    route_plan = SimpleNamespace(
        id=32,
        label="Plan for March 31",
        date_strategy="single",
        plan_type=None,
        start_date=datetime(2026, 3, 31, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
        orders=[],
    )
    order_1 = SimpleNamespace(
        id=1,
        client_address={"coordinates": {"lat": 59.1, "lng": 18.1}},
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 31, 14, 0, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 31, 18, 0, 0, tzinfo=timezone.utc),
            )
        ],
    )
    order_2 = SimpleNamespace(
        id=2,
        client_address={"coordinates": {"lat": 59.2, "lng": 18.2}},
        delivery_windows=[],
    )
    route_plan.orders = [order_1, order_2]

    stop_1 = _make_stop(
        101,
        1,
        1,
        datetime(2026, 3, 31, 13, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 31, 13, 0, 0, tzinfo=timezone.utc),
    )
    stop_2 = _make_stop(
        102,
        2,
        2,
        datetime(2026, 3, 31, 13, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 31, 13, 30, 0, tzinfo=timezone.utc),
    )
    stop_1.order = order_1
    stop_2.order = order_2
    route_solution = _make_route_solution(route_plan, [stop_1, stop_2])

    delta = OrderUpdateDelta(
        order_instance=order_1,
        old_values={},
        new_values={},
        flags=OrderUpdateChangeFlags(window_changed=True),
        delivery_plan=route_plan,
    )
    extension_context = OrderUpdateExtensionContext(
        by_plan_type={
            "local_delivery": {
                "route_stops_by_order_id": {1: [stop_1]},
                "route_solutions_by_id": {10: route_solution},
            }
        }
    )

    result = handle_local_delivery_order_update_extension(
        ctx=SimpleNamespace(),
        order_deltas=[delta],
        extension_context=extension_context,
    )

    for action in result.post_flush_actions:
        action()

    bundle = result.bundle_by_order_id[1]
    serialized_stops = bundle["order_stops"]
    serialized_route = bundle["route_solution"][0]

    assert stop_1.expected_arrival_time == datetime(2026, 3, 31, 14, 0, 0, tzinfo=timezone.utc)
    assert stop_2.expected_arrival_time == datetime(2026, 3, 31, 14, 30, 0, tzinfo=timezone.utc)
    assert route_solution.expected_end_time == datetime(2026, 3, 31, 14, 35, 0, tzinfo=timezone.utc)
    assert [stop["id"] for stop in serialized_stops] == [101, 102]
    assert serialized_route["expected_end_time"] == "2026-03-31T14:35:00+00:00"
