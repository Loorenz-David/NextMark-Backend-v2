from sqlalchemy.orm import selectinload

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Order, RouteGroup, RoutePlan, RouteSolution, RouteSolutionStop, db

from ...context import ServiceContext
from ..get_instance import get_instance
from ..route_solutions.serialize_route_solution_stops import serialize_route_solution_stops
from ..route_solutions.serialize_route_solutions import serialize_route_solution


def _unwrap_single_serialized_stop(serialized_stop):
    if not serialized_stop:
        return None

    if isinstance(serialized_stop, list):
        return serialized_stop[0] if serialized_stop else None

    if isinstance(serialized_stop, dict):
        by_client_id = serialized_stop.get("byClientId")
        all_ids = serialized_stop.get("allIds")
        if isinstance(by_client_id, dict) and isinstance(all_ids, list) and all_ids:
            return by_client_id.get(str(all_ids[0]))

        if "id" in serialized_stop:
            return serialized_stop

    raise ValidationFailed("Unexpected serialized route_solution_stop shape.")


def get_order_route_context(order_id: int, ctx: ServiceContext) -> dict:
    order = get_instance(ctx=ctx, model=Order, value=order_id)

    selected_stops = (
        db.session.query(RouteSolutionStop)
        .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
        .options(
            selectinload(RouteSolutionStop.route_solution)
            .selectinload(RouteSolution.route_group)
            .selectinload(RouteGroup.route_plan)
        )
        .filter(
            RouteSolutionStop.order_id == order.id,
            RouteSolutionStop.team_id == ctx.team_id,
            RouteSolution.team_id == ctx.team_id,
            RouteSolution.is_selected.is_(True),
        )
        .order_by(
            RouteSolution.updated_at.desc(),
            RouteSolution.id.desc(),
            RouteSolutionStop.stop_order.asc(),
            RouteSolutionStop.id.asc(),
        )
        .all()
    )

    if not selected_stops:
        raise NotFound(f"No selected route solution found for order with id: {order_id}.")

    route_solution_ids = {
        stop.route_solution_id for stop in selected_stops if stop.route_solution_id is not None
    }
    if len(route_solution_ids) != 1:
        raise ValidationFailed(
            f"Expected exactly one selected route solution for order with id: {order_id}."
        )

    if len(selected_stops) != 1:
        raise ValidationFailed(
            f"Expected exactly one selected route stop for order with id: {order_id}."
        )

    route_stop = selected_stops[0]
    route_solution = getattr(route_stop, "route_solution", None)
    if route_solution is None:
        raise NotFound(
            f"Selected route solution could not be loaded for order with id: {order_id}."
        )

    serialized_stop = _unwrap_single_serialized_stop(
        serialize_route_solution_stops([route_stop], ctx)
    )

    return {
        "order_id": order.id,
        "route_solution": serialize_route_solution(route_solution),
        "route_solution_stop": serialized_stop,
        "route_plan_id": getattr(getattr(route_solution, "route_group", None), "route_plan_id", None),
        "route_group_id": getattr(route_solution, "route_group_id", None),
    }
