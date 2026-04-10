from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import Order, RoutePlan, RouteSolution, RouteSolutionStop, db


def touch_route_freshness(route_plan: RoutePlan | None) -> datetime | None:
    if route_plan is None:
        return None

    now = datetime.now(timezone.utc)
    route_plan.updated_at = now
    return now


def touch_route_freshness_by_route(route_solution: RouteSolution | None) -> datetime | None:
    if route_solution is None:
        return None

    route_group = getattr(route_solution, "route_group", None)
    if route_group is None:
        return None

    route_plan = getattr(route_group, "route_plan", None)
    return touch_route_freshness(route_plan)


def touch_route_freshness_by_stop(route_stop: RouteSolutionStop | None) -> datetime | None:
    if route_stop is None or route_stop.route_solution_id is None:
        return None

    route_solution = db.session.get(RouteSolution, route_stop.route_solution_id)
    return touch_route_freshness_by_route(route_solution)


def touch_route_freshness_by_order(order: Order | None) -> datetime | None:
    if order is None:
        return None

    route_plan_id = getattr(order, "route_plan_id", None)
    if route_plan_id is None:
        return None

    route_plan = getattr(order, "route_plan", None)
    if route_plan is None:
        route_plan = db.session.get(RoutePlan, route_plan_id)
    return touch_route_freshness(route_plan)


def get_route_freshness_updated_at(route_plan: RoutePlan | None) -> str | None:
    if route_plan is None or route_plan.updated_at is None:
        return None

    return route_plan.updated_at.isoformat()
