from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    route_group_snapshot_name,
)
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.order.serialize_order import serialize_orders
from Delivery_app_BK.services.queries.route_plan.plan_types.serialize_route_group import (
    serialize_route_groups,
)
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions_mixed,
)


def local_delivery_overview(ctx: ServiceContext, plan_id: int):
    try:
        plan: RoutePlan = get_instance(ctx=ctx, model=RoutePlan, value=plan_id)
    except NoResultFound:
        raise NotFound(f"Route plan {plan_id} not found.")
    route_groups = sorted(
        list(getattr(plan, "route_groups", None) or []),
        key=lambda group: (
            route_group_snapshot_name(getattr(group, "zone_geometry_snapshot", None)) or "",
            getattr(group, "id", 10**9),
        ),
    )
    if not route_groups:
        raise ValidationFailed("Route group not found.")

    requested_route_group_id = _parse_route_group_id(ctx)
    selected_route_group = _select_route_group(route_groups, requested_route_group_id)

    selected_route_solution = next(
        (
            solution
            for solution in (selected_route_group.route_solutions or [])
            if solution.is_selected
        ),
        None,
    )
    if not selected_route_solution:
        route_solutions = sorted(
            list(selected_route_group.route_solutions or []),
            key=lambda solution: (
                getattr(solution, "id", 10**9),
                getattr(solution, "client_id", ""),
            ),
        )
        if not route_solutions:
            raise ValidationFailed("Route group has no route solutions.")
        selected_route_solution = route_solutions[0]
        ctx.set_warning(
            "Route group had no selected route solution. Falling back to the first available route."
        )

    orders = list(plan.orders or [])
    stops = list(selected_route_solution.stops or [])
    other_route_solutions = [
        solution
        for solution in (selected_route_group.route_solutions or [])
        if solution.id != selected_route_solution.id
    ]

    return {
        "order": serialize_orders(orders, ctx),
        "route_group": serialize_route_groups(route_groups, ctx),
        "route_solution": serialize_route_solutions_mixed(
            selected_route_solution,
            other_route_solutions,
            ctx,
        ),
        "route_solution_stop": serialize_route_solution_stops(stops, ctx),
    }


def _parse_route_group_id(ctx: ServiceContext) -> int | None:
    raw_value = (ctx.query_params or {}).get("route_group_id")
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, bool):
        raise ValidationFailed("route_group_id must be an integer")
    if isinstance(raw_value, int):
        parsed = raw_value
    elif isinstance(raw_value, str) and raw_value.strip().isdigit():
        parsed = int(raw_value.strip())
    else:
        raise ValidationFailed("route_group_id must be an integer")
    if parsed <= 0:
        raise ValidationFailed("route_group_id must be greater than 0")
    return parsed


def _select_route_group(route_groups: list, route_group_id: int | None):
    if route_group_id is None:
        return route_groups[0]

    for route_group in route_groups:
        if getattr(route_group, "id", None) == route_group_id:
            return route_group

    raise ValidationFailed(f"route_group_id {route_group_id} does not belong to route plan")
