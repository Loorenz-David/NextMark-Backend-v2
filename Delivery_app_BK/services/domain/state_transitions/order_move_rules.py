"""
order_move_rules
================
Encodes the full state-heritage matrix for when an order is moved into a
delivery plan.  All functions are pure (no DB access, no side effects), so
they are trivial to unit-test.

The public API is:
  compute_destination_move_result(order, destination_plan, now)
    -> OrderMoveResult

Callers (e.g. update_order_route_plan) are responsible for:
  1. Calling this function for each moved order.
  2. Applying the returned state changes via update_orders_state / apply_plan_state.
  3. Optionally creating an OrderCase when result.should_create_case is True.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId

if TYPE_CHECKING:
    from Delivery_app_BK.models import RoutePlan
    from Delivery_app_BK.models.tables.order.order import Order


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OrderMoveResult:
    """
    Describes what state changes (if any) should be applied after moving one
    order into a destination delivery plan.
    """
    # None means: leave the order's state unchanged.
    new_order_state_id: int | None = None
    # None means: leave the plan's state unchanged.
    new_plan_state_id: int | None = None
    # When True the caller should create an OrderCase on the order.
    should_create_case: bool = False
    # Predefined case text to prepend to any user-supplied message.
    case_predefined_text: str | None = None


# ---------------------------------------------------------------------------
# Matrix implementation
# ---------------------------------------------------------------------------

def compute_destination_move_result(
    order: "Order",
    destination_plan: "RoutePlan",
    now: datetime | None = None,
) -> OrderMoveResult:
    """
    Apply the state-heritage matrix and return what changes are needed.

    Matrix (order state → plan state):

    Plan: COMPLETED
      order COMPLETED         → no change
      order not COMPLETED, plan_end in past  → order → COMPLETED
      order not COMPLETED, plan_end not past → plan → PROCESSING

    Plan: PROCESSING
      any order state         → order → PROCESSING

    Plan: OPEN
            order PROCESSING        → order → CONFIRMED
      order COMPLETED         → order → CONFIRMED
      other order state       → no change

    Plan: READY
      order READY             → no change
      order PROCESSING        → order → FAIL, plan → OPEN, create_case=True
      other order state       → plan → OPEN

    Plan: FAIL
      any order state         → no change (no specific rule defined)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    plan_state_id = getattr(destination_plan, "state_id", None)
    order_state_id = getattr(order, "order_state_id", None)

    is_order_completed = order_state_id == OrderStateId.COMPLETED

    # ---- COMPLETED plan ----
    if plan_state_id == PlanStateId.COMPLETED:
        if is_order_completed:
            return OrderMoveResult()
        plan_end = getattr(destination_plan, "end_date", None)
        plan_end_in_past = _is_in_past(plan_end, now)
        if plan_end_in_past:
            return OrderMoveResult(new_order_state_id=OrderStateId.COMPLETED)
        return OrderMoveResult(new_plan_state_id=PlanStateId.PROCESSING)

    # ---- PROCESSING plan ----
    if plan_state_id == PlanStateId.PROCESSING:
        return OrderMoveResult(new_order_state_id=OrderStateId.PROCESSING)

    # ---- OPEN plan ----
    if plan_state_id == PlanStateId.OPEN:
        if is_order_completed:
            return OrderMoveResult(new_order_state_id=OrderStateId.CONFIRMED)
        if order_state_id == OrderStateId.PROCESSING:
            return OrderMoveResult(new_order_state_id=OrderStateId.CONFIRMED)
        return OrderMoveResult()

    # ---- READY plan ----
    if plan_state_id == PlanStateId.READY:
        if order_state_id == OrderStateId.READY:
            return OrderMoveResult()
        if order_state_id == OrderStateId.PROCESSING:
            return OrderMoveResult(
                new_order_state_id=OrderStateId.FAIL,
                new_plan_state_id=PlanStateId.OPEN,
                should_create_case=True,
                case_predefined_text=_build_processing_order_moved_to_ready_plan_text(order, destination_plan),
            )
        # Any other state: reset plan to OPEN
        return OrderMoveResult(new_plan_state_id=PlanStateId.OPEN)

    # ---- FAIL or unknown plan state ----
    return OrderMoveResult()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_in_past(dt: datetime | None, now: datetime) -> bool:
    if dt is None:
        return False
    # Normalise to UTC-aware for comparison.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < now


def _build_processing_order_moved_to_ready_plan_text(
    order: "Order",
    plan: "RoutePlan",
) -> str:
    order_ref = getattr(order, "reference_number", None) or f"#{order.id}"
    plan_label = getattr(plan, "label", None) or f"Plan #{plan.id}"
    return (
        f"Order {order_ref} was moved into plan '{plan_label}' which is marked as Ready for Delivery. "
        f"Because the order was in Processing state it has been marked as Failed "
        f"and the plan has been reset to Open."
    )
