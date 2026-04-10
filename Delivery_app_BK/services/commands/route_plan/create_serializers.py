from datetime import datetime

from Delivery_app_BK.models import (
    RoutePlan,
    RouteGroup,
    RouteSolution,
)
from Delivery_app_BK.services.queries.utils import calculate_plan_metrics


def _to_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat()


def serialize_created_route_plan(instance: RoutePlan) -> dict:
    serialized = {
        "id": instance.id,
        "client_id": instance.client_id,
        "label": instance.label,
        "date_strategy": instance.date_strategy,
        "start_date": _to_iso(instance.start_date),
        "end_date": _to_iso(instance.end_date),
        "created_at": _to_iso(instance.created_at),
        "updated_at": _to_iso(instance.updated_at),
        "state_id": instance.state_id,
        "item_type_counts": instance.item_type_counts,
    }
    serialized.update(calculate_plan_metrics(instance))
    return serialized


def serialize_created_delivery_plan(instance: RoutePlan) -> dict:
    # Backward-compatible alias while route_plan naming is rolled out.
    return serialize_created_route_plan(instance)


def serialize_created_route_group(instance: RouteGroup) -> dict:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "route_plan_id": instance.route_plan_id,
        "state_id": instance.state_id,
        "total_weight_g": instance.total_weight_g,
        "total_volume_cm3": instance.total_volume_cm3,
        "total_item_count": instance.total_item_count,
        "total_orders": instance.total_orders,
        "order_state_counts": instance.order_state_counts,
        "item_type_counts": instance.item_type_counts,
    }


def serialize_created_route_solution(instance: RouteSolution) -> dict:
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
        "has_route_warnings": instance.has_route_warnings,
        "route_warnings": instance.route_warnings,
        "start_location": instance.start_location,
        "end_location": instance.end_location,
        "expected_start_time": _to_iso(instance.expected_start_time),
        "expected_end_time": _to_iso(instance.expected_end_time),
        "actual_start_time": _to_iso(instance.actual_start_time),
        "actual_end_time": _to_iso(instance.actual_end_time),
        "set_start_time": instance.set_start_time,
        "set_end_time": instance.set_end_time,
        "eta_tolerance_seconds": instance.eta_tolerance_seconds,
        "eta_message_tolerance": instance.eta_message_tolerance if instance.eta_message_tolerance is not None else 1800,
        "stops_service_time": instance.stops_service_time,
        "is_selected": instance.is_selected,
        "is_optimized": instance.is_optimized,
        "driver_id": instance.driver_id,
        "route_end_strategy": instance.route_end_strategy,
        "route_group_id": instance.route_group_id,
        "created_at": _to_iso(instance.created_at),
        "updated_at": _to_iso(instance.updated_at),
    }
