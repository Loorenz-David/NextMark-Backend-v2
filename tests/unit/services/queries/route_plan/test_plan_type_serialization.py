from __future__ import annotations

from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.create_serializers import (
    serialize_created_route_plan,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
    serialize_route_solution_partial,
)


def _created_plan(plan_type: str):
    return SimpleNamespace(
        id=3,
        client_id="route_plan:3",
        label="Plan A",
        plan_type=plan_type,
        date_strategy="single",
        start_date=None,
        end_date=None,
        created_at=None,
        updated_at=None,
        state_id=1,
        item_type_counts=None,
        total_orders=None,
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        orders=[],
        route_groups=[],
    )


def _route_solution(route_plan):
    route_group = SimpleNamespace(id=8, route_plan_id=3, route_plan=route_plan)
    return SimpleNamespace(
        id=5,
        client_id="route_solution:5",
        label="Route 1",
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
        eta_tolerance_seconds=None,
        eta_message_tolerance=None,
        stops_service_time=None,
        is_selected=True,
        is_optimized=False,
        driver=None,
        driver_id=None,
        vehicle_id=None,
        route_end_strategy=None,
        route_group_id=8,
        route_group=route_group,
        created_at=None,
        updated_at=None,
    )


def test_created_plan_payload_carries_the_plan_type():
    serialized = serialize_created_route_plan(_created_plan("international_shipping"))

    assert serialized["plan_type"] == "international_shipping"


def test_route_solution_reports_the_owning_plan_type_not_a_constant():
    # Previously this emitted the literal "route_plan" for every plan regardless
    # of type, which made the field meaningless to consumers.
    route_plan = _created_plan("store_pickup")

    assert serialize_route_solution(_route_solution(route_plan))["plan_type"] == "store_pickup"
    assert (
        serialize_route_solution_partial(_route_solution(route_plan))["plan_type"]
        == "store_pickup"
    )


def test_route_solution_plan_type_is_none_without_a_plan():
    assert serialize_route_solution(_route_solution(None))["plan_type"] is None
    assert serialize_route_solution_partial(_route_solution(None))["plan_type"] is None
