from typing import List
from Delivery_app_BK.models import LabelTemplate

from ....context import ServiceContext
from ...utils import map_return_values


def serialize_label_templates(instances: List[LabelTemplate], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "enable": instance.enable,
            "channel": instance.channel,
            "selected_variant": instance.selected_variant,
            "event": instance.event,
            "ask_permission": instance.ask_permission,
            "orientation": instance.orientation,
            "is_system": instance.is_system,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "label_template")


def serialize_label_templates_bootstrap(instances: List[LabelTemplate], ctx: ServiceContext):
    unpacked_instances = []
    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "enable": instance.enable,
            "channel": instance.channel,
            "event": instance.event,
            "orientation": instance.orientation,
            "selected_variant": instance.selected_variant,
            "ask_permission": instance.ask_permission,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "label_template")

