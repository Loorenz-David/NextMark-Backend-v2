from typing import List
from Delivery_app_BK.models import ItemPosition

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_item_positions(instances: List[ItemPosition], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "default": instance.default,
            "description": instance.description,
            "is_system": instance.is_system,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "item_position")
