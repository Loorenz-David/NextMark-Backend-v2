from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    normalize_route_group_zone_snapshot,
    route_group_snapshot_name,
)
from Delivery_app_BK.services.queries.get_instance import get_instance


def _serialize_selected_route_solution(route_group):
    route_solutions = list(getattr(route_group, "route_solutions", None) or [])
    if not route_solutions:
        return None

    selected = next(
        (solution for solution in route_solutions if getattr(solution, "is_selected", False)),
        route_solutions[0],
    )
    return {
        "id": selected.id,
        "version": selected.version,
        "is_selected": selected.is_selected,
        "is_optimized": selected.is_optimized,
        "total_distance_meters": selected.total_distance_meters,
        "total_travel_time_seconds": selected.total_travel_time_seconds,
        "stop_count": len(selected.stops or []),
        "order_count": route_group.total_orders or 0,
    }


def _serialize_route_group(route_group) -> dict:
    zone = getattr(route_group, "zone", None)
    state = getattr(route_group, "state", None)
    raw_snapshot = getattr(route_group, "zone_geometry_snapshot", None)
    zone_snapshot = normalize_route_group_zone_snapshot(raw_snapshot)
    return {
        "id": route_group.id,
        "client_id": route_group.client_id,
        "zone_id": getattr(route_group, "zone_id", None),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(route_group, "template_snapshot", None),
        "updated_at": route_group.updated_at.isoformat() if route_group.updated_at else None,
        "route_plan_id": route_group.route_plan_id,
        "state": {
            "id": state.id,
            "name": state.name,
        }
        if state is not None
        else None,
        "total_orders": route_group.total_orders,
        "item_type_counts": route_group.item_type_counts,
        "zone": {
            "id": zone.id,
            "name": zone.name,
            "city_key": zone.city_key,
            "geometry": zone.geometry,
        }
        if zone is not None
        else None,
        "active_route_solution": _serialize_selected_route_solution(route_group),
    }


def list_route_groups(route_plan_id: int, ctx: ServiceContext) -> dict:
    """
    Returns the route groups attached to a route plan.
    """
    try:
        route_plan: RoutePlan = get_instance(ctx=ctx, model=RoutePlan, value=route_plan_id)
    except NoResultFound:
        raise NotFound(f"Route plan {route_plan_id} not found.")

    route_groups = sorted(
        list(route_plan.route_groups or []),
        key=lambda group: (
            0 if getattr(group, "zone_id", None) is None else 1,
            (route_group_snapshot_name(getattr(group, "zone_geometry_snapshot", None)) or "").lower(),
            (group.id or 0),
        ),
    )
    serialized = [_serialize_route_group(route_group) for route_group in route_groups]

    return {
        "route_plan_id": route_plan_id,
        "route_groups": serialized,
    }
