from Delivery_app_BK.services.commands.order.order_states.update_orders_state import (
    update_orders_state,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_states import OrderStateId

from ._helpers import resolve_driver_action_order_stop
from .serializers import serialize_driver_order_command_delta


def undo_driver_order_terminal(ctx: ServiceContext, order_id: int):
    order, _stop = resolve_driver_action_order_stop(ctx, order_id)

    changed_orders = update_orders_state(
        ctx=ctx,
        orders=[order],
        state_id=OrderStateId.PROCESSING,
    )

    return {
        "orders": serialize_driver_order_command_delta(
            instances=changed_orders,
            ctx=ctx,
        ),
    }
