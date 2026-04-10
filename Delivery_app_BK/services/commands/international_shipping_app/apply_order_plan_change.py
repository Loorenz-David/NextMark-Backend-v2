"""International Shipping App - Order Plan Change Handler (no-op).

International shipping plans do not require custom plan change processing.
"""

from ...context import ServiceContext
from ..order.plan_changes.types import PlanChangeApplyContext, PlanChangeResult


def apply_order_plan_change(
    ctx: ServiceContext,
    order_instance,
    old_plan,
    new_plan,
    apply_context: PlanChangeApplyContext,
) -> PlanChangeResult:
    """International shipping plans don't require plan change processing.
    
    Returns an empty result.
    """
    return PlanChangeResult()
