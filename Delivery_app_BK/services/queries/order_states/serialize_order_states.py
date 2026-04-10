from typing import List
from Delivery_app_BK.models import OrderState

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_order_states(instances: List[ OrderState ], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "color": instance.color,
            "index": instance.index,
            "is_system": instance.is_system,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "order_state")
