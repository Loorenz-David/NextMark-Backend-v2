from typing import Type, List
from flask_sqlalchemy.model import Model
from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    route_group_snapshot_name,
)

from ...context import ServiceContext
from ..utils import map_return_values, calculate_plan_metrics


def _serialize_route_group_summary(route_group) -> dict:
    state = getattr(route_group, "state", None)
    snapshot_name = route_group_snapshot_name(
        getattr(route_group, "zone_geometry_snapshot", None)
    )
    return {
        "id": route_group.id,
        "name": snapshot_name,
        "zone_id": getattr(route_group, "zone_id", None),
        "total_orders": getattr(route_group, "total_orders", None),
        "item_type_counts": getattr(route_group, "item_type_counts", None),
        "state": (
            {
                "id": state.id,
                "name": getattr(state, "name", None),
            }
            if state is not None
            else None
        ),
    }


def serialize_plans(
    instances: List[Type[RoutePlan]],
    ctx: ServiceContext,
    *,
    include_route_groups_summary: bool = False,
):
    
    unpacked_instances = []

    for instance in instances:
        start_date = instance.start_date
        end_date = instance.end_date
        created_at = instance.created_at
        route_groups = sorted(
            list(getattr(instance, "route_groups", None) or []),
            key=lambda route_group: (
                0 if getattr(route_group, "zone_id", None) is None else 1,
                route_group_snapshot_name(getattr(route_group, "zone_geometry_snapshot", None)) or "",
                getattr(route_group, "id", 0) or 0,
            ),
        )
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "label": instance.label,
            "date_strategy": instance.date_strategy,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
            "state_id": instance.state_id,
            "route_groups_count": len(route_groups),
        }
        unpacked.update(calculate_plan_metrics(instance))
        if instance.total_orders is not None:
            unpacked.update({
                "total_weight": instance.total_weight_g,
                "total_volume": instance.total_volume_cm3,
                "total_items": instance.total_item_count,
                "total_orders": instance.total_orders,
                "item_type_counts": instance.item_type_counts,
            })
        if include_route_groups_summary:
            unpacked["route_groups"] = [
                _serialize_route_group_summary(route_group)
                for route_group in route_groups
            ]

        unpacked_instances.append( unpacked )

    return map_return_values(unpacked_instances, ctx, "route_plan")
