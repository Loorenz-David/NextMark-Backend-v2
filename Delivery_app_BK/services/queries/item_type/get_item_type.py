from Delivery_app_BK.models import ItemType
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_item_types import serialize_item_types


def get_item_type(type_id: int, ctx: ServiceContext):
    found_type = get_instance(
        ctx=ctx,
        model=ItemType,
        value=type_id,
    )

    if not found_type:
        raise NotFound(f"Item type with id: {type_id} does not exist.")

    serialized = serialize_item_types(
        instances=[found_type],
        ctx=ctx,
    )

    return {
        "item_type": serialized[0] if isinstance(serialized, list) else serialized
    }
