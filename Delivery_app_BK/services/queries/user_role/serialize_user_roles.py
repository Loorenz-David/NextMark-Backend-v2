from typing import List
from Delivery_app_BK.models import UserRole

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_user_roles(instances: List[UserRole], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "role_name": instance.role_name,
            "description": instance.description,
            "is_system": instance.is_system,
            "base_role_id": instance.base_role_id,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "user_role")
