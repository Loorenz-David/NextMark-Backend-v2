from typing import List
from Delivery_app_BK.models import TeamInvites

from ....context import ServiceContext
from ...utils import map_return_values


def serialize_team_invites_sent(instances: List[TeamInvites], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        invite_date = instance.creation_date
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "target_username": instance.target_username,
            "target_email": instance.target_email,
            "user_role_name": instance.user_role_name,
            "creation_date": invite_date.isoformat() if invite_date else None,
        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "team_invites_sent")
