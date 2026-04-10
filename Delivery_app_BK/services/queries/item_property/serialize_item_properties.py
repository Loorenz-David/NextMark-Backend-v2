from typing import List
from Delivery_app_BK.models import ItemProperty

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_item_properties(instances: List[ ItemProperty ], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "field_type": instance.field_type,
            "options": instance.options,
            "required": instance.required,
            "item_types": [it.id for it in instance.item_types],
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "item_property")
