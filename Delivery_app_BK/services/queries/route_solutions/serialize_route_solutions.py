from typing import List

from Delivery_app_BK.models import RouteSolution
from ...context import ServiceContext
from ..utils import map_return_values


def serialize_route_solution(instance: RouteSolution) -> dict:
    created_at = instance.created_at
    expected_start_time = instance.expected_start_time
    expected_end_time = instance.expected_end_time
    actual_start_time = instance.actual_start_time
    actual_end_time = instance.actual_end_time
    driver = getattr(instance, "driver", None)
    route_group = getattr(instance, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    route_group_id = getattr(instance, "route_group_id", None)
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "_representation": "full",
        "label": instance.label,
        "version": instance.version,
        "algorithm": instance.algorithm,
        "score": instance.score,
        "total_distance_meters": instance.total_distance_meters,
        "total_travel_time_seconds": instance.total_travel_time_seconds,
        "start_leg_polyline": instance.start_leg_polyline,
        "end_leg_polyline": instance.end_leg_polyline,
        "has_route_warnings": bool(instance.route_warnings),
        "route_warnings": instance.route_warnings,
        "start_location": instance.start_location,
        "end_location": instance.end_location,
        "expected_start_time": expected_start_time.isoformat() if expected_start_time else None,
        "expected_end_time": expected_end_time.isoformat() if expected_end_time else None,
        "actual_start_time": actual_start_time.isoformat() if actual_start_time else None,
        "actual_end_time": actual_end_time.isoformat() if actual_end_time else None,
        "set_start_time": instance.set_start_time,
        "set_end_time": instance.set_end_time,
        "eta_tolerance_seconds": instance.eta_tolerance_seconds,
        "eta_message_tolerance": instance.eta_message_tolerance if instance.eta_message_tolerance is not None else 1800,
        "stops_service_time": instance.stops_service_time,
        "is_selected": instance.is_selected,
        "is_optimized": instance.is_optimized,
        "driver_id": instance.driver_id,
        "driver_name": getattr(driver, "username", None),
        "vehicle_id": instance.vehicle_id,
        "route_end_strategy": instance.route_end_strategy,
        "route_group_id": route_group_id,
        "route_plan_id": getattr(route_group, "route_plan_id", None),
        "plan_label": getattr(route_plan, "label", None),
        "date_strategy": getattr(route_plan, "date_strategy", None),
        "plan_type": getattr(route_plan, "plan_type", None),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


def serialize_route_solution_partial(instance: RouteSolution) -> dict:
    driver = getattr(instance, "driver", None)
    route_group = getattr(instance, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    route_group_id = getattr(instance, "route_group_id", None)
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "route_group_id": route_group_id,
        "_representation": "partial",
        "label": instance.label,
        "driver_name": getattr(driver, "username", None),
        "plan_label": getattr(route_plan, "label", None),
        "date_strategy": getattr(route_plan, "date_strategy", None),
        "plan_type": getattr(route_plan, "plan_type", None),
        "score": instance.score,
        "total_distance_meters": instance.total_distance_meters,
        "total_travel_time_seconds": instance.total_travel_time_seconds,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


def serialize_route_solutions(instances: List[RouteSolution], ctx: ServiceContext):
    unpacked_instances = [serialize_route_solution(instance) for instance in instances]
    return map_return_values(unpacked_instances, ctx, "route_solution")


def serialize_route_solutions_mixed(
    selected_solution: RouteSolution,
    other_solutions: List[RouteSolution],
    ctx: ServiceContext,
):

    unpacked_instances = [serialize_route_solution(selected_solution)]
    unpacked_instances.extend(
        serialize_route_solution_partial(instance) for instance in other_solutions
    )
    return map_return_values(unpacked_instances, ctx, "route_solution")
