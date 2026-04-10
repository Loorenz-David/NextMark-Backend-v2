from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.commands.order.order_states.update_orders_state import (
    update_orders_state,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.queries.get_instance import get_instance


def ready_for_delivery(
    ctx: ServiceContext,
    route_plan_id: int,
) -> dict:
    delivery_plan: RoutePlan = get_instance(
        ctx=ctx,
        model=RoutePlan,
        value=route_plan_id,
    )

    if delivery_plan.state_id == PlanStateId.READY:
        return {}

    delivery_plan.state_id = PlanStateId.READY

    _TERMINAL_ORDER_STATE_IDS = {OrderStateId.COMPLETED, OrderStateId.CANCELLED}
    eligible_orders = [
        o for o in (delivery_plan.orders or [])
        if o.order_state_id not in _TERMINAL_ORDER_STATE_IDS
    ]
    update_orders_state(
        ctx=ctx,
        orders=eligible_orders,
        state_id=OrderStateId.READY,
    )

    return {"failed_order_state_updates": {}}
