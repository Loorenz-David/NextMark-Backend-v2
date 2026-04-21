from typing import List
from Delivery_app_BK.models import Order
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState
from Delivery_app_BK.services.domain.order.delivery_windows import (
    sort_delivery_window_instances,
)

from ...context import ServiceContext
from ..item.serialize_items import serialize_items
from ..utils import map_return_values, calculate_order_metrics


def _count_open_order_cases(order: Order) -> int:
    cases = getattr(order, "order_cases", None) or []
    return sum(1 for case in cases if case.state != OrderCaseState.RESOLVED.value)


def _serialize_order_instance(instance: Order, ctx: ServiceContext, include_items: bool = False):
    creation_date = instance.creation_date
    delivery_windows = sort_delivery_window_instances(
        list(getattr(instance, "delivery_windows", None) or []),
    )
    unpacked = {
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
        "external_tracking_number": instance.external_tracking_number,
        "external_tracking_link": instance.external_tracking_link,
        "client_first_name": instance.client_first_name,
        "client_last_name": instance.client_last_name,
        "client_email": instance.client_email,
        "client_primary_phone": instance.client_primary_phone,
        "client_secondary_phone": instance.client_secondary_phone,
        "client_address": instance.client_address,
        "marketing_messages": instance.marketing_messages,
        "creation_date": creation_date.isoformat() if creation_date else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        "items_updated_at": instance.items_updated_at.isoformat() if instance.items_updated_at else None,
        "order_state_id": instance.order_state_id,
        "route_plan_id": instance.route_plan_id,
        "route_group_id": instance.route_group_id,
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
        "client_form_submitted_at": instance.client_form_submitted_at.isoformat() if instance.client_form_submitted_at else None,
        "order_notes": list(instance.order_notes) if instance.order_notes else [],
    }
    if instance.archive_at is not None:
        unpacked['archive_at'] = instance.archive_at

    if include_items:
        unpacked["items"] = serialize_items(
            instances=list(getattr(instance, "items", None) or []),
            ctx=ctx,
        )

    # Read denormalized totals; fall back to computed metrics for unbackfilled rows
    if instance.total_weight_g is not None or instance.total_volume_cm3 is not None or instance.total_item_count is not None:
        unpacked["total_weight"] = instance.total_weight_g
        unpacked["total_volume"] = instance.total_volume_cm3
        unpacked["total_items"] = instance.total_item_count
    else:
        unpacked.update(calculate_order_metrics(instance))
    return unpacked


def serialize_orders( instances: List[ Order ], ctx:ServiceContext  ):
    unpacked_instances = []

    for instance in instances:
        unpacked_instances.append(_serialize_order_instance(instance, ctx))

        

    return map_return_values(unpacked_instances, ctx, "order")


def serialize_orders_with_items(instances: List[Order], ctx: ServiceContext):
    unpacked_instances = [
        _serialize_order_instance(instance, ctx, include_items=True)
        for instance in instances
    ]

    return map_return_values(unpacked_instances, ctx, "order")
