from __future__ import annotations

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.context import ServiceContext


def get_execution_status(ctx: ServiceContext, plan: RoutePlan) -> dict:
    """
    Execution status for store_pickup plans.
    Future: return pickup slot info, customer queue, readiness status, etc.
    """
    return {
        "status": "not_implemented",
        "plan_id": plan.id,
        "plan_type": plan.plan_type,
        "message": "Store pickup execution status is not yet available.",
    }
