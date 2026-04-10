"""International Shipping App - Order Objective Handler (no-op).

International shipping plans do not require custom order objective processing.
"""

from ...context import ServiceContext
from ..order.plan_objectives.types import PlanObjectiveCreateResult


def apply_order_objective(
    ctx: ServiceContext,
    order_instance,
    delivery_plan,
    plan_objective: str,
) -> PlanObjectiveCreateResult:
    """International shipping plans don't require order objective processing.
    
    Returns an empty result.
    """
    return PlanObjectiveCreateResult()
