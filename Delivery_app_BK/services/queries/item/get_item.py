from Delivery_app_BK.models import db, Item
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance 
from .serialize_items import serialize_items


def get_item(item_id: int, ctx: ServiceContext):
    found_item = get_instance(
        ctx = ctx,
        model = Item,
        value = item_id
    )

    if not found_item:
        raise NotFound(f"Item with id: {item_id} does not exist.")

    serialized = serialize_items(
        instances=[found_item],
        ctx=ctx,
    )

    return {
        "item": serialized[0] if isinstance(serialized, list) else serialized
    }
