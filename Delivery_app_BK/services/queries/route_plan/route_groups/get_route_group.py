from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import RouteGroup, RoutePlan, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    normalize_route_group_zone_snapshot,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
    serialize_route_solution_partial,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solution_stops import (
    serialize_route_solution_stops,
)


def _serialize_route_group_detail(route_group: RouteGroup) -> dict:
    zone = getattr(route_group, "zone", None)
    state = getattr(route_group, "state", None)
    zone_snapshot = normalize_route_group_zone_snapshot(
        getattr(route_group, "zone_geometry_snapshot", None)
    )
    return {
        "id": route_group.id,
        "client_id": route_group.client_id,
        "route_plan_id": route_group.route_plan_id,
        "zone_id": getattr(route_group, "zone_id", None),
        "is_system_default_bucket": getattr(route_group, "is_system_default_bucket", False),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(route_group, "template_snapshot", None),
        "updated_at": (
            route_group.updated_at.isoformat() if route_group.updated_at else None
        ),
        "state": (
            {"id": state.id, "name": state.name} if state is not None else None
        ),
        "total_orders": route_group.total_orders,
        "item_type_counts": route_group.item_type_counts,
        "zone": (
            {
                "id": zone.id,
                "name": zone.name,
                "city_key": zone.city_key,
                "geometry": zone.geometry,
            }
            if zone is not None
            else None
        ),
    }


def get_route_group(
    route_plan_id: int,
    route_group_id: int,
    ctx: ServiceContext,
) -> dict:
    route_plan = db.session.get(RoutePlan, route_plan_id)
    if route_plan is None or route_plan.team_id != ctx.team_id:
        raise NotFound(f"Route plan {route_plan_id} not found.")

    route_group = db.session.get(RouteGroup, route_group_id)
    if (
        route_group is None
        or route_group.team_id != ctx.team_id
        or route_group.route_plan_id != route_plan_id
    ):
        raise NotFound(f"Route group {route_group_id} not found.")

    all_solutions = list(getattr(route_group, "route_solutions", None) or [])
    selected = next(
        (s for s in all_solutions if getattr(s, "is_selected", False)),
        all_solutions[0] if all_solutions else None,
    )
    others = [s for s in all_solutions if s is not selected]

    route_solutions = []
    route_solution_stops = []

    if selected is not None:
        route_solutions.append(serialize_route_solution(selected))
        route_solution_stops = serialize_route_solution_stops(
            list(selected.stops or []), ctx
        )

    for solution in others:
        route_solutions.append(serialize_route_solution_partial(solution))

    return {
        "route_group": _serialize_route_group_detail(route_group),
        "route_solutions": route_solutions,
        "route_solution_stops": route_solution_stops,
    }
