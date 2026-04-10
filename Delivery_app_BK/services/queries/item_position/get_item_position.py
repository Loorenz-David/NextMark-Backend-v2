from Delivery_app_BK.models import ItemPosition
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_item_positions import serialize_item_positions


def get_item_position(position_id: int, ctx: ServiceContext):
    found_position = get_instance(
        ctx=ctx,
        model=ItemPosition,
        value=position_id,
    )

    if not found_position:
        raise NotFound(f"Item position with id: {position_id} does not exist.")

    serialized = serialize_item_positions(
        instances=[found_position],
        ctx=ctx,
    )

    return {
        "item_position": serialized[0] if isinstance(serialized, list) else serialized
    }
