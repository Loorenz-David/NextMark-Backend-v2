from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.order_states.update_orders_state import (
    update_orders_state,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_states import OrderStateId

from ._helpers import resolve_driver_action_order_stop
from .serializers import (
    serialize_driver_order_command_delta,
)

def fail_driver_order(ctx: ServiceContext, order_id: int):
    incoming_data = ctx.incoming_data or {}
    description = incoming_data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValidationFailed("description is required.")

    order, _stop = resolve_driver_action_order_stop(ctx, order_id)

    state_ctx = ServiceContext(
        incoming_data={
            "order_notes": {
                "type": "FAILURE",
                "content": description.strip(),
            }
        },
        identity=ctx.identity,
        check_team_id=ctx.check_team_id,
        inject_team_id=ctx.inject_team_id,
        skip_id_instance_injection=ctx.skip_id_instance_injection,
    )

    changed_orders = update_orders_state(
        ctx=state_ctx,
        orders=[order],
        state_id=OrderStateId.FAIL,
    )

    return {
        "orders": serialize_driver_order_command_delta(
            instances=changed_orders,
            ctx=ctx,
        ),
    }
