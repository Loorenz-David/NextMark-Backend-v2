from types import SimpleNamespace

from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)


def test_serialize_route_solution_includes_eta_message_tolerance_default():
    instance = SimpleNamespace(
        id=1,
        client_id="route_solution_1",
        label="variant 1",
        version=1,
        algorithm=None,
        score=None,
        total_distance_meters=None,
        total_travel_time_seconds=None,
        start_leg_polyline=None,
        end_leg_polyline=None,
        route_warnings=None,
        start_location=None,
        end_location=None,
        expected_start_time=None,
        expected_end_time=None,
        actual_start_time=None,
        actual_end_time=None,
        set_start_time=None,
        set_end_time=None,
        eta_tolerance_seconds=0,
        eta_message_tolerance=None,
        stops_service_time=None,
        is_selected=True,
        is_optimized="not_optimized",
        driver_id=None,
        driver=None,
        vehicle_id=None,
        route_end_strategy="round_trip",
        route_group_id=5,
        route_group=None,
        created_at=None,
        updated_at=None,
    )

    serialized = serialize_route_solution(instance)

    assert serialized["eta_message_tolerance"] == 1800
