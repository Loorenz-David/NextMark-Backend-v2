from typing import List

from Delivery_app_BK.models import RoutePlan, RouteSolution
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.plan_types.serialize_route_group import (
    serialize_route_group,
)
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution,
)
from Delivery_app_BK.services.queries.utils import map_return_values


def _serialize_route_plan_collapsed(instance: RoutePlan | None):
    if instance is None:
        return None

    start_date = instance.start_date
    end_date = instance.end_date
    created_at = instance.created_at
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "label": instance.label,
        "date_strategy": getattr(instance, "date_strategy", None),
        "plan_type": getattr(instance, "plan_type", None),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        "state_id": instance.state_id,
    }


def serialize_active_route(instance: RouteSolution, ctx: ServiceContext):
    route_group = getattr(instance, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group else None

    serialized_route_plan = _serialize_route_plan_collapsed(route_plan)

    unpacked = {
        **serialize_route_solution(instance),
        "route_plan": serialized_route_plan,
        "route_group": (
            serialize_route_group(route_group, ctx)
            if route_group is not None
            else None
        ),
    }

    return unpacked


def serialize_active_route_summary(instance: RouteSolution, ctx: ServiceContext):
    route_group = getattr(instance, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group else None
    created_at = instance.created_at
    updated_at = instance.updated_at
    route_group_id = getattr(instance, "route_group_id", None)

    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "_representation": "summary",
        "is_selected": bool(instance.is_selected),
        "driver_id": instance.driver_id,
        "route_group_id": route_group_id,
        "route_solution_id": instance.id,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "route_plan": _serialize_route_plan_collapsed(route_plan),
    }


def serialize_active_routes(instances: List[RouteSolution], ctx: ServiceContext):
    unpacked_instances = [
        serialize_active_route_summary(instance, ctx)
        for instance in instances
    ]

    return map_return_values(unpacked_instances, ctx, "route")
