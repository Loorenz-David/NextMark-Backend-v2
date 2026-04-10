from typing import List
from Delivery_app_BK.models import Item

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_items(instances: List[ Item ], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "article_number": instance.article_number,
            "reference_number": instance.reference_number,
            "item_type": instance.item_type,
            "item_state_id": instance.item_state_id,
            "item_position_id": instance.item_position_id,
            "order_id": instance.order_id,
            "properties": instance.properties,
            "page_link": instance.page_link,
            "dimension_depth": instance.dimension_depth ,
            "dimension_height": instance.dimension_height ,
            "dimension_width": instance.dimension_width ,
            "weight": instance.weight,
            "quantity": instance.quantity

        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "item")
