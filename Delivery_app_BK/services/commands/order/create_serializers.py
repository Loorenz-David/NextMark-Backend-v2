from Delivery_app_BK.models import Item, Order, RouteSolutionStop
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState
from Delivery_app_BK.services.domain.order.delivery_windows import (
    sort_delivery_window_instances,
)
from Delivery_app_BK.services.queries.utils import calculate_order_metrics


def _order_totals(instance: Order) -> dict:
    """Read denormalized totals; fall back to computed for unbackfilled rows."""
    if (
        instance.total_weight_g is not None
        or instance.total_volume_cm3 is not None
        or instance.total_item_count is not None
    ):
        return {
            "total_weight": instance.total_weight_g,
            "total_volume": instance.total_volume_cm3,
            "total_items": instance.total_item_count,
        }
    return calculate_order_metrics(instance)


def serialize_created_order(instance: Order) -> dict:
    creation_date = instance.creation_date
    archive_at = instance.archive_at
    metrics = _order_totals(instance)
    delivery_windows = sort_delivery_window_instances(
        list(getattr(instance, "delivery_windows", None) or []),
    )

    route_plan_id = getattr(instance, "route_plan_id", None)
    delivery_plan_id = getattr(instance, "delivery_plan_id", route_plan_id)

    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "order_plan_objective": instance.order_plan_objective,
        "operation_type": instance.operation_type,
        "order_scalar_id": instance.order_scalar_id,
        "reference_number": instance.reference_number,
        "external_order_id": instance.external_order_id,
        "external_source": instance.external_source,
        "tracking_number": instance.tracking_number,
        "tracking_link": instance.tracking_link,
        "client_first_name": instance.client_first_name,
        "client_last_name": instance.client_last_name,
        "client_email": instance.client_email,
        "client_primary_phone": instance.client_primary_phone,
        "client_secondary_phone": instance.client_secondary_phone,
        "client_address": instance.client_address,
        "marketing_messages": instance.marketing_messages,
        "creation_date": creation_date.isoformat() if creation_date else None,
        "items_updated_at": instance.items_updated_at.isoformat() if instance.items_updated_at else None,
        "order_state_id": instance.order_state_id,
        "route_plan_id": route_plan_id,
        "delivery_plan_id": delivery_plan_id,
        "costumer_id": instance.costumer_id,
        "delivery_windows": [
            {
                "id": row.id,
                "client_id": row.client_id,
                "start_at": row.start_at.isoformat() if row.start_at else None,
                "end_at": row.end_at.isoformat() if row.end_at else None,
                "window_type": row.window_type,
            }
            for row in delivery_windows
        ],
        "open_order_cases": _count_open_order_cases(instance),
        "archive_at": archive_at.isoformat() if archive_at else None,
        **metrics,
    }


def serialize_created_items(instances: list[Item]) -> list[dict]:
    return [
        {
            "id": instance.id,
            "client_id": instance.client_id,
            "article_number": instance.article_number,
            "reference_number": instance.reference_number,
            "item_type": instance.item_type,
            "item_state_id": instance.item_state_id,
            "item_position_id": instance.item_position_id,
            "order_id": instance.order_id,
            "properties": instance.properties,
            "page_link": instance.page_link,
            "dimension_depth": instance.dimension_depth,
            "dimension_height": instance.dimension_height,
            "dimension_width": instance.dimension_width,
            "weight": instance.weight,
            "quantity": instance.quantity,
        }
        for instance in instances
    ]


def serialize_created_order_stops(instances: list[RouteSolutionStop]) -> list[dict]:
    return [
        {
            "id": instance.id,
            "client_id": instance.client_id,
            "route_solution_id": instance.route_solution_id,
            "order_id": instance.order_id,
            "service_duration": instance.service_duration,
            "service_time": getattr(instance, "service_time", instance.service_duration),
            "in_range": getattr(instance, "in_range", None),
            "stop_order": getattr(instance, "stop_order", None),
            "reason_was_skipped": getattr(instance, "reason_was_skipped", None),
            "has_constraint_violation": getattr(instance, "has_constraint_violation", None),
            "constraint_warnings": getattr(instance, "constraint_warnings", None),
            "eta_status": getattr(instance, "eta_status", None),
            "expected_arrival_time": getattr(instance, "expected_arrival_time", None).isoformat()
            if getattr(instance, "expected_arrival_time", None)
            else None,
            "expected_departure_time": getattr(instance, "expected_departure_time", None).isoformat()
            if getattr(instance, "expected_departure_time", None)
            else None,
            "expected_service_duration_seconds": getattr(instance, "expected_service_duration_seconds", None),
            "actual_arrival_time": getattr(instance, "actual_arrival_time", None).isoformat()
            if getattr(instance, "actual_arrival_time", None)
            else None,
            "actual_departure_time": getattr(instance, "actual_departure_time", None).isoformat()
            if getattr(instance, "actual_departure_time", None)
            else None,
            "to_next_polyline": getattr(instance, "to_next_polyline", None),
        }
        for instance in instances
    ]


def _count_open_order_cases(order: Order) -> int:
    cases = getattr(order, "order_cases", None) or []
    return sum(1 for case in cases if case.state != OrderCaseState.RESOLVED.value)
