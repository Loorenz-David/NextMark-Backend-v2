from Delivery_app_BK.models import ItemState
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_item_states import serialize_item_states


def get_item_state(state_id: int, ctx: ServiceContext):
    found_state = get_instance(
        ctx=ctx,
        model=ItemState,
        value=state_id,
    )

    if not found_state:
        raise NotFound(f"Item state with id: {state_id} does not exist.")

    serialized = serialize_item_states(
        instances=[found_state],
        ctx=ctx,
    )

    return {
        "item_state": serialized[0] if isinstance(serialized, list) else serialized
    }
