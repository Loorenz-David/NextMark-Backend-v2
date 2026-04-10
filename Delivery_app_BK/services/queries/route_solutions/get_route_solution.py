from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import RouteGroup, RoutePlan, RouteSolution, db

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_route_solutions import serialize_route_solution, serialize_route_solutions
from .serialize_route_solution_stops import serialize_route_solution_stops


def get_route_solution(route_solution_id: int, ctx: ServiceContext, return_stops: bool = False):
    if route_solution_id is None:
        raise ValidationFailed("Missing route_solution_id.")
    found_solution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=route_solution_id,
    )

    if not found_solution:
        raise NotFound(f"Route solution with id: {route_solution_id} does not exist.")

    if not getattr(found_solution, "is_selected", False):
        raise ValidationFailed("Route solution is not selected.")

    serialized = serialize_route_solutions(
        instances=[found_solution],
        ctx=ctx,
    )

    response = {
        "route_solution": serialized[0] if isinstance(serialized, list) else serialized
    }

    if return_stops:
        stops = list(found_solution.stops or [])
        response["route_solution_stop"] = serialize_route_solution_stops(stops, ctx)

    return response


def get_route_solution_with_stops(
    route_plan_id: int,
    route_group_id: int,
    route_solution_id: int,
    ctx: ServiceContext,
) -> dict:
    """Return a single route solution (full shape) with all its stops.

    Validates route-plan → route-group → route-solution ownership before
    returning data.  Does not require the solution to be selected.
    """
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

    solution = db.session.get(RouteSolution, route_solution_id)
    if (
        solution is None
        or solution.team_id != ctx.team_id
        or solution.route_group_id != route_group_id
    ):
        raise NotFound(f"Route solution {route_solution_id} not found.")

    stops = list(solution.stops or [])
    return {
        "route_solution": serialize_route_solution(solution),
        "route_solution_stops": serialize_route_solution_stops(stops, ctx),
    }
