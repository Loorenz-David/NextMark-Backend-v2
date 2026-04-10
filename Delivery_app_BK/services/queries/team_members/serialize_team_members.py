from typing import List
from Delivery_app_BK.models import User

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_team_members(instances: List[User], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        last_online = instance.last_online
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "username": instance.username,
            "email": instance.email,
            "phone_number": instance.phone_number,
            "user_role_id": instance.user_role_id,
            "profile_picture": instance.profile_picture,
            "show_app_tutorial": instance.show_app_tutorial,
            "last_online": last_online.isoformat() if last_online else None,
            "last_location": instance.last_location,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "team_member")
