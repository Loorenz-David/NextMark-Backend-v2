"""
order_count_engine
==================
Centralised computation of per-state order counts for route groups and their
parent delivery plans. Supports multiple plan types via a dispatcher dict so
future plan types (international_shipping, store_pickup, …) only need a new
entry in PLAN_COUNT_HANDLERS.

No commits are issued — callers are responsible for flushing / committing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Any

from Delivery_app_BK.models import RoutePlan, RouteSolution, Order, OrderState, db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route-group level
# ---------------------------------------------------------------------------

def recompute_route_group_order_counts(route_solution_or_group: Any) -> None:
    """
    Query the DB for all orders currently assigned to this route group and
    group them by their state name. Sets denormalized counters on the route
    group:
      - route_group.total_orders       (total distinct orders)
      - route_group.order_state_counts (dict[state_name, count])

    Does NOT flush / commit.
    """
    if route_solution_or_group is None:
        return

    route_group = getattr(route_solution_or_group, "route_group", None)
    if route_group is None and getattr(route_solution_or_group, "id", None) is not None:
        route_group = route_solution_or_group
    if route_group is None:
        return

    rows = (
        db.session.query(OrderState.name, db.func.count(Order.id.distinct()))
        .select_from(Order)
        .join(OrderState, Order.order_state_id == OrderState.id)
        .filter(Order.route_group_id == route_group.id)
        .group_by(OrderState.name)
        .all()
    )

    counts: dict[str, int] = {}
    total = 0
    for state_name, count in rows:
        if state_name:
            counts[state_name] = int(count)
            total += int(count)

    route_group.total_orders = total
    route_group.order_state_counts = counts or None

    logger.debug(
        "recompute_route_group_order_counts route_group_id=%s total=%s counts=%s",
        route_group.id,
        total,
        counts,
    )


def recompute_route_solution_order_counts(route_solution: "RouteSolution") -> None:
    """Backward-compatible alias for callers still using the old name."""
    recompute_route_group_order_counts(route_solution)


# ---------------------------------------------------------------------------
# Plan-type dispatcher
# ---------------------------------------------------------------------------

PlanCountHandler = Callable[["RoutePlan"], None]

def _recompute_local_delivery_counts(plan: "RoutePlan") -> None:
    """Find the selected route solution for this local delivery plan and recompute."""
    local = getattr(plan, "local_delivery", None)
    if local is None:
        return

    route_solutions = (
        db.session.query(RouteSolution)
        .filter(RouteSolution.route_group_id == local.id)
        .order_by(RouteSolution.is_selected.desc(), RouteSolution.id.asc())
        .all()
    )
    if not route_solutions:
        local.total_orders = 0
        local.order_state_counts = None
        return

    selected = next((rs for rs in route_solutions if rs.is_selected), route_solutions[0])
    recompute_route_group_order_counts(selected)


# Extend this dict when new plan types gain route-solution–like sub-tables.
_PLAN_COUNT_HANDLERS: dict[str, PlanCountHandler] = {
    "local_delivery": _recompute_local_delivery_counts,
}


def recompute_plan_order_counts(plan: "RoutePlan") -> None:
    """
    Dispatch to the correct plan-type handler to recompute order counts.
    No-ops gracefully if the plan type has no registered handler yet.
    """
    if plan is None or plan.id is None:
        return

    handler = _PLAN_COUNT_HANDLERS.get(getattr(plan, "plan_type", None))
    if handler is None:
        return

    handler(plan)

    logger.debug(
        "recompute_plan_order_counts plan_id=%s plan_type=%s",
        plan.id,
        plan.plan_type,
    )
