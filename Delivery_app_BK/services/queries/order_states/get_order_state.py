from Delivery_app_BK.models import OrderState
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_order_states import serialize_order_states


def get_order_state(state_id: int, ctx: ServiceContext):
    found_state = get_instance(
        ctx=ctx,
        model=OrderState,
        value=state_id,
    )

    if not found_state:
        raise NotFound(f"Order state with id: {state_id} does not exist.")

    serialized = serialize_order_states(
        instances=[found_state],
        ctx=ctx,
    )

    return {
        "order_state": serialized[0] if isinstance(serialized, list) else serialized
    }
