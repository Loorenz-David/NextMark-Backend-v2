"""
plan_state_engine
=================
Pure-function helpers for deriving and applying delivery-plan states.

None of these functions issue DB commits or flushes — that is the caller's
responsibility.

Rules encoded here:
  - A plan auto-completes when its selected route solution has at least one
    order and all of them are in the Completed state.
  - A plan should reset to Open when its dates, times, or locations are
    changed and it is not already Open.
  - `apply_plan_state` is the single safe setter — it is a no-op when the
    state is already correct.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Delivery_app_BK.models import RouteGroup, db
from Delivery_app_BK.services.domain.order.order_states import OrderState as OrderStateEnum
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId

if TYPE_CHECKING:
    from Delivery_app_BK.models import RoutePlan
    from Delivery_app_BK.models import RouteGroup
    from Delivery_app_BK.models import RouteSolution

logger = logging.getLogger(__name__)

_COMPLETED_STATE_NAME = OrderStateEnum.COMPLETED.value


def derive_auto_complete_state(route_group: "RouteGroup | None") -> int | None:
    """
    Return PlanStateId.COMPLETED if all orders in the route group are
    completed, otherwise return None.

    Preconditions:
      - route_group.total_orders and route_group.order_state_counts must
        already have been recomputed before calling this function.
    """
    if route_group is None:
        return None

    total = route_group.total_orders or 0
    if total == 0:
        return None

    counts = route_group.order_state_counts or {}
    completed = counts.get(_COMPLETED_STATE_NAME, 0)

    if completed >= total:
        return PlanStateId.COMPLETED

    return None


def get_selected_route_solution(plan: "RoutePlan") -> "RouteSolution | None":
    """Return the first selected RouteSolution across the plan's route groups."""
    route_groups = list(getattr(plan, "route_groups", None) or [])
    for route_group in route_groups:
        route_solutions = getattr(route_group, "route_solutions", None) or []
        selected = next((rs for rs in route_solutions if rs.is_selected), None)
        if selected is not None:
            return selected
        if route_solutions:
            return route_solutions[0]
    return None


def should_reset_plan_to_open(current_state_id: int | None) -> bool:
    """Return True if the plan is in any state other than Open."""
    return current_state_id != PlanStateId.OPEN


def apply_plan_state(plan: "RoutePlan", state_id: int) -> bool:
    """
    Set plan.state_id to state_id if it differs.  Returns True when changed.
    Does NOT flush or commit.
    """
    if plan is None:
        return False
    if plan.state_id == state_id:
        return False
    plan.state_id = state_id
    logger.debug(
        "apply_plan_state plan_id=%s %s -> %s",
        plan.id,
        plan.state_id,
        state_id,
    )
    return True


def maybe_auto_complete_plan(plan: "RoutePlan") -> bool:
    """
    Check if the plan should auto-transition to COMPLETED and apply it.
    Must be called *after* `recompute_plan_order_counts`.
    Returns True when the plan was transitioned.
    """
    if plan is None:
        return False

    # Allows manual completion flows where orders are marked completed
    # without first transitioning the plan to PROCESSING.

    route_solution = get_selected_route_solution(plan)
    route_group = getattr(route_solution, "route_group", None) if route_solution else None
    auto_state = derive_auto_complete_state(route_group)
    if auto_state is None:
        return False

    return apply_plan_state(plan, auto_state)


def derive_plan_state_from_groups(plan: "RoutePlan") -> int:
    """Derive plan state from surviving persisted route groups using strict all-match rules."""
    if plan is None or getattr(plan, "id", None) is None:
        return PlanStateId.OPEN

    groups = (
        db.session.query(RouteGroup)
        .filter(RouteGroup.route_plan_id == plan.id)
        .all()
    )
    if not groups:
        return PlanStateId.OPEN

    state_ids = {group.state_id for group in groups}
    if len(state_ids) == 1:
        sole = next(iter(state_ids))
        if sole in (PlanStateId.COMPLETED, PlanStateId.PROCESSING, PlanStateId.READY):
            return sole
    return PlanStateId.OPEN


def maybe_sync_plan_state_from_groups(plan: "RoutePlan") -> bool:
    """Derive and apply plan state from route groups; returns True when changed."""
    derived_state_id = derive_plan_state_from_groups(plan)
    return apply_plan_state(plan, derived_state_id)
