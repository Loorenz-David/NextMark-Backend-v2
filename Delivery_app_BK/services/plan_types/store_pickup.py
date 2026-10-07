from ..commands.store_pickup_app import (
    apply_order_delete_extension,
    apply_order_objective,
    apply_order_plan_change,
    apply_order_update_extension,
)
from .contract import PlanTypeModule, no_order_realtime_extras

STORE_PICKUP = PlanTypeModule(
    plan_type="store_pickup",
    apply_objective=apply_order_objective,
    apply_plan_change=apply_order_plan_change,
    apply_order_update=apply_order_update_extension,
    apply_order_delete=apply_order_delete_extension,
    build_order_realtime_extras=no_order_realtime_extras,
)
