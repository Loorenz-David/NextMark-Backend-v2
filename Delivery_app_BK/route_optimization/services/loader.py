from __future__ import annotations
from datetime import datetime, timezone
from Delivery_app_BK.errors import ValidationFailed, NotFound
from sqlalchemy.orm import selectinload
from Delivery_app_BK.models import RouteGroup, RouteSolution, RoutePlan, Order, db
from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
from Delivery_app_BK.route_optimization.domain.models import OptimizationContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP, CUSTOM_END_ADDRESS
def _ensure_utc(value: datetime | None) -> datetime | None:
    if not value:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _normalize_legacy_single_day_end_date(
    route_plan: RoutePlan,
    end_date: datetime | None,
) -> datetime | None:
    if not end_date:
        return end_date

    if getattr(route_plan, "date_strategy", None) != "single":
        return end_date

    start_date = _ensure_utc(getattr(route_plan, "start_date", None))
    if not start_date:
        return end_date

    # Legacy broken writes stored single-day plans at 00:00:00 instead of end-of-day.
    # Treat those rows as same-day route windows until the data is rewritten cleanly.
    if (
        end_date.date() == start_date.date()
        and end_date.hour == 0
        and end_date.minute == 0
        and end_date.second == 0
        and end_date.microsecond == 0
    ):
        return end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    return end_date


def load_optimization_context(ctx:ServiceContext) -> OptimizationContext:
    incoming_data = ctx.incoming_data or {}
    route_group_id = incoming_data.get("route_group_id")
    if route_group_id is None:
        raise ValidationFailed("Missing route_group_id.")

    route_group = get_instance(
        ctx=ctx,
        model=RouteGroup,
        value=route_group_id,
    )
    route_plan: RoutePlan = route_group.route_plan
    if not route_plan:
        raise ValidationFailed("Route group is missing route plan.")

    is_route_solution_end_date_valid(route_plan)

    route_solution = _select_route_solution(route_group)

    orders = (
        db.session.query(Order)
        .options(selectinload(Order.delivery_windows), selectinload(Order.items))
        .filter(Order.route_plan_id == route_plan.id)
        .all()
    )
    if not orders:
        raise ValidationFailed("Route plan has no orders to optimize.")

    route_end_strategy = (incoming_data.get("route_end_strategy") or
                          route_solution.route_end_strategy or
                          ROUND_TRIP
                          )

    vehicle = None
    if getattr(route_solution, "vehicle_id", None):
        vehicle = db.session.get(Vehicle, route_solution.vehicle_id)

    return OptimizationContext(
        route_group=route_group,
        route_plan=route_plan,
        route_solution=route_solution,
        orders=orders,
        identity=ctx.identity,
        incoming_data=incoming_data,
        route_end_strategy = route_end_strategy,
        interpret_injected_solutions_using_labels=bool(
            incoming_data.get("interpret_injected_solutions_using_labels", True)
        ),
        return_shape=str(incoming_data.get("return_shape") or "map_ids_object"),
        ctx=ctx,
        vehicle=vehicle,
    )


def _select_route_solution(route_group: RouteGroup) -> RouteSolution:
    route_solutions = list(route_group.route_solutions or [])
    if not route_solutions:
        raise ValidationFailed("Route group has no route solutions.")

    for route_solution in route_solutions:
        if getattr(route_solution, "is_selected", False):
            return route_solution

    raise ValidationFailed("Route group has no selected route solution.")


def is_route_solution_end_date_valid (route_plan: RoutePlan):
    try:

        if route_plan:
            now = datetime.now(timezone.utc)
            start_date = _ensure_utc(route_plan.start_date) or now
            end_date = _ensure_utc(route_plan.end_date) or start_date
            end_date = _normalize_legacy_single_day_end_date(route_plan, end_date)
            
    except Exception:
        raise NotFound('route solution has no route group or route group has no route plan linked.')

    if end_date < now:
        raise ValidationFailed('This route has already ended and cannot be optimized. Update the route plan end date to a future time to re-optimize.')
