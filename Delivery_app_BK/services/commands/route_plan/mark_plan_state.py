from Delivery_app_BK.models import RoutePlan
from ...context import ServiceContext
from Delivery_app_BK.services.commands.order.order_states.update_orders_state import update_orders_state
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from ...domain.order.order_states import OrderStateId
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import apply_plan_state
from Delivery_app_BK.services.queries.order import build_state_update_payload


def mark_plan_state(
        ctx: ServiceContext,
        route_plan_id: int,
        state_id: PlanStateId
):
        plan: RoutePlan = get_instance(ctx, RoutePlan, route_plan_id)

        if not apply_plan_state(plan, state_id):
                return build_state_update_payload(
                        route_plans=[plan],
                )

        changed_orders = []
        if state_id == PlanStateId.READY:
                _TERMINAL_ORDER_STATE_IDS = {OrderStateId.COMPLETED, OrderStateId.CANCELLED}
                eligible_orders = [
                        o for o in (plan.orders or [])
                        if o.order_state_id not in _TERMINAL_ORDER_STATE_IDS
                ]
                changed_orders = update_orders_state(
                        ctx=ctx,
                        orders=eligible_orders,
                        state_id=OrderStateId.READY,
                )

        return build_state_update_payload(
                changed_orders=changed_orders,
                route_plans=[plan],
        )
