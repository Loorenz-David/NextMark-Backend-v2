
from Delivery_app_BK.models import User
from Delivery_app_BK.services.domain.user import (
    has_team_workspace_available,
    resolve_app_workspace_context,
)

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_user(instance: User, ctx: ServiceContext):

    
    last_online = instance.last_online
    workspace_context = (
        resolve_app_workspace_context(instance, ctx.app_scope)
        if ctx.app_scope in {"admin", "driver"}
        else {
            "current_workspace": None,
            "has_team_workspace": has_team_workspace_available(instance),
        }
    )
    unpacked_instances = [{
        "id": instance.id,
        "client_id": instance.client_id,
        "username": instance.username,
        "email": instance.email,
        "phone_number": instance.phone_number,
        "user_role_id": instance.user_role_id,
        "team_id": instance.team_id,
        "profile_picture": instance.profile_picture,
        "current_workspace": workspace_context["current_workspace"],
        "has_team_workspace": workspace_context["has_team_workspace"],
        "show_app_tutorial": instance.show_app_tutorial,
    }]
    mapped_instances = map_return_values(unpacked_instances, ctx, "user")
    return mapped_instances[0] if isinstance(mapped_instances, list) else mapped_instances
