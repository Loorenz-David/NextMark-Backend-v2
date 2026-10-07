from ..commands.international_shipping_app import (
    apply_order_delete_extension,
    apply_order_objective,
    apply_order_plan_change,
    apply_order_update_extension,
)
from .contract import PlanTypeModule, no_order_realtime_extras

INTERNATIONAL_SHIPPING = PlanTypeModule(
    plan_type="international_shipping",
    apply_objective=apply_order_objective,
    apply_plan_change=apply_order_plan_change,
    apply_order_update=apply_order_update_extension,
    apply_order_delete=apply_order_delete_extension,
    build_order_realtime_extras=no_order_realtime_extras,
)
