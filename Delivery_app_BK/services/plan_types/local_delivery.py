from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import (
    build_order_route_freshness_extras,
)

from ..commands.local_delivery_app import (
    apply_order_delete_extension,
    apply_order_objective,
    apply_order_update_extension,
)
from ..commands.order.plan_changes.route_plan_change import apply_route_plan_change
from .contract import PlanTypeModule

LOCAL_DELIVERY = PlanTypeModule(
    plan_type="local_delivery",
    apply_objective=apply_order_objective,
    apply_plan_change=apply_route_plan_change,
    apply_order_update=apply_order_update_extension,
    apply_order_delete=apply_order_delete_extension,
    build_order_realtime_extras=build_order_route_freshness_extras,
)
