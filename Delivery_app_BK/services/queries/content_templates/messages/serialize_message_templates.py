from typing import List
from Delivery_app_BK.models import MessageTemplate

from ....context import ServiceContext
from ...utils import map_return_values


def serialize_message_templates(instances: List[MessageTemplate], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "event":instance.event,
            "enable":instance.enable,
            "template":instance.template,
            "ask_permission": instance.ask_permission,
            "name":instance.name,
            "channel": instance.channel,
            "schedule_offset_value": instance.schedule_offset_value,
            "schedule_offset_unit": instance.schedule_offset_unit,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "message_template")

def serialize_message_templates_bootstrap(instances: List[MessageTemplate], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "event":instance.event,
            "enable":instance.enable,
            "ask_permission": instance.ask_permission,
            "channel": instance.channel,
            "schedule_offset_value": instance.schedule_offset_value,
            "schedule_offset_unit": instance.schedule_offset_unit,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "message_template")
