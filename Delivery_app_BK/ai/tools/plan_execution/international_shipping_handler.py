from __future__ import annotations

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.context import ServiceContext


def get_execution_status(ctx: ServiceContext, plan: RoutePlan) -> dict:
    """
    Execution status for international_shipping plans.
    Future: wire to external vendor/carrier APIs here (DHL, FedEx, etc.).
    """
    return {
        "status": "not_implemented",
        "plan_id": plan.id,
        "plan_type": plan.plan_type,
        "message": "International shipping execution status is not yet available. Vendor integration coming soon.",
    }
