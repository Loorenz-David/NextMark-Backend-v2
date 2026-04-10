from datetime import datetime, timezone

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Order, RouteSolution, RouteSolutionStop, db
from Delivery_app_BK.routers.utils.role_decorator import ADMIN
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.utils import require_team_id


def resolve_driver_action_order_stop(ctx: ServiceContext, order_id: int) -> tuple[Order, RouteSolutionStop]:
    team_id = require_team_id(ctx)

    query = (
        db.session.query(RouteSolutionStop, Order)
        .join(Order, RouteSolutionStop.order_id == Order.id)
        .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
        .filter(
            Order.id == order_id,
            Order.team_id == team_id,
            RouteSolutionStop.team_id == team_id,
            RouteSolution.team_id == team_id,
            RouteSolution.is_selected.is_(True),
        )
        .order_by(RouteSolutionStop.stop_order.asc(), RouteSolutionStop.id.asc())
    )

    if ctx.base_role_id != ADMIN:
        query = query.filter(RouteSolution.driver_id == ctx.user_id)

    resolved = query.first()
    
    if resolved is None:
        raise NotFound(f"Order {order_id} is not actionable for this driver workspace.")

    stop, order = resolved
    return order, stop


def resolve_driver_route_solution(ctx: ServiceContext, route_id: int) -> RouteSolution:
    team_id = require_team_id(ctx)

    query = (
        db.session.query(RouteSolution)
        .filter(
            RouteSolution.id == route_id,
            RouteSolution.team_id == team_id,
            RouteSolution.is_selected.is_(True),
        )
    )

    if ctx.base_role_id != ADMIN:
        query = query.filter(RouteSolution.driver_id == ctx.user_id)

    route_solution = query.first()
    if route_solution is None:
        raise NotFound(f"Route {route_id} is not actionable for this driver workspace.")

    return route_solution


def resolve_driver_route_stop(ctx: ServiceContext, stop_client_id: str) -> RouteSolutionStop:
    team_id = require_team_id(ctx)

    query = (
        db.session.query(RouteSolutionStop)
        .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
        .filter(
            RouteSolutionStop.client_id == stop_client_id,
            RouteSolutionStop.team_id == team_id,
            RouteSolution.team_id == team_id,
            RouteSolution.is_selected.is_(True),
        )
        .order_by(RouteSolutionStop.stop_order.asc(), RouteSolutionStop.id.asc())
    )

    if ctx.base_role_id != ADMIN:
        query = query.filter(RouteSolution.driver_id == ctx.user_id)

    route_stop = query.first()
    if route_stop is None:
        raise NotFound(f"Stop {stop_client_id} is not actionable for this driver workspace.")

    return route_stop


def is_within_route_window(route_solution: RouteSolution, candidate_time: datetime) -> bool:
    candidate = candidate_time.astimezone(timezone.utc) if candidate_time.tzinfo else candidate_time.replace(tzinfo=timezone.utc)
    expected_start_time = getattr(route_solution, "expected_start_time", None)
    expected_end_time = getattr(route_solution, "expected_end_time", None)

    start = (
        expected_start_time.astimezone(timezone.utc)
        if isinstance(expected_start_time, datetime) and expected_start_time.tzinfo
        else expected_start_time.replace(tzinfo=timezone.utc)
        if isinstance(expected_start_time, datetime)
        else None
    )
    end = (
        expected_end_time.astimezone(timezone.utc)
        if isinstance(expected_end_time, datetime) and expected_end_time.tzinfo
        else expected_end_time.replace(tzinfo=timezone.utc)
        if isinstance(expected_end_time, datetime)
        else None
    )

    if start is None and end is None:
        route_group = getattr(route_solution, "route_group", None)
        route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
        start_date = getattr(route_plan, "start_date", None)
        end_date = getattr(route_plan, "end_date", None)
        if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
            return False
        start = start_date.astimezone(timezone.utc) if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
        end = end_date.astimezone(timezone.utc) if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
    elif start is not None and end is None:
        end = start
    elif start is None and end is not None:
        start = end

    if start is None or end is None:
        return False

    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start <= candidate <= end
