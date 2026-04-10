from typing import List
from Delivery_app_BK.models import ItemType

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_item_types(instances: List[ ItemType ], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "properties":[prop.id for prop in instance.properties],
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "item_type")
