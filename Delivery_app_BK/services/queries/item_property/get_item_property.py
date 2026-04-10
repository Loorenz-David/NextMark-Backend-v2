from Delivery_app_BK.models import ItemProperty
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_item_properties import serialize_item_properties


def get_item_property(property_id: int, ctx: ServiceContext):
    found_property = get_instance(
        ctx=ctx,
        model=ItemProperty,
        value=property_id,
    )

    if not found_property:
        raise NotFound(f"Item property with id: {property_id} does not exist.")

    serialized = serialize_item_properties(
        instances=[found_property],
        ctx=ctx,
    )

    return {
        "item_property": serialized[0] if isinstance(serialized, list) else serialized
    }
