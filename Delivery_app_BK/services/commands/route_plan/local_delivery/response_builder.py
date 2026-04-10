from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions,
)


def build_local_delivery_settings_response(
    ctx: ServiceContext,
    route_solution: RouteSolution,
    stops_changed: bool,
    route_solution_changed: bool,
) -> dict:
    if not route_solution_changed and not stops_changed:
        return {}

    response = {
        "route_solution": serialize_route_solutions([route_solution], ctx),
    }
    if stops_changed:
        response["route_solution_stops"] = serialize_route_solution_stops(
            list(route_solution.stops or []),
            ctx,
        )

    return response


def build_route_group_settings_response(
    ctx: ServiceContext,
    route_solution: RouteSolution,
    stops_changed: bool,
    route_solution_changed: bool,
) -> dict:
    return build_local_delivery_settings_response(
        ctx=ctx,
        route_solution=route_solution,
        stops_changed=stops_changed,
        route_solution_changed=route_solution_changed,
    )
