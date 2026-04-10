from typing import Type
from flask_sqlalchemy.model import Model

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_order_state_transition_rules(instances: Type[Model], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "allowed_state_id": instance.allowed_state_id,
            "user_role_id": instance.user_role_id,

        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "order_state_transition_rule")
