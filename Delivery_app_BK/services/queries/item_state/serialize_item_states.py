from typing import List
from Delivery_app_BK.models import ItemState

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_item_states(instances: List[ ItemState], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "color": instance.color,
            "default": instance.default,
            "description": instance.description,
            "index": instance.index,
            "is_system": instance.is_system,
            "entry_point": instance.entry_point,

        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "item_state")
