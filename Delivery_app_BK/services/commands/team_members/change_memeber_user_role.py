from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import User, UserRole, db
from Delivery_app_BK.services.domain.user import (
    resolve_user_team_membership,
    sync_all_app_workspace_states,
)

from ...context import ServiceContext
from ..utils import extract_fields


def change_memeber_user_role(ctx: ServiceContext):
    fields = extract_fields(ctx, return_single=True)
    if not isinstance(fields, dict):
        raise ValidationFailed("Fields must be provided as a dictionary.")

    user_id = fields.get("user_id")
    user_role_id = fields.get("user_role_id")
    if not user_id or not user_role_id:
        raise ValidationFailed("user_id and user_role_id are required.")

    user_role = get_instance(ctx, UserRole, user_role_id)
    if not user_role:
        raise NotFound(f"User role with id '{user_role_id}' was not found.")

    user = db.session.get(User, user_id)
    if not user:
        raise NotFound(f"User with id '{user_id}' was not found.")

    membership = resolve_user_team_membership(user, ctx.team_id)
    if not membership["is_member"]:
        raise ValidationFailed("User does not belong to this team.")

    if membership["is_active_workspace"]:
        user.user_role_id = user_role.id
    else:
        user.team_workspace_role_id = user_role.id

    sync_all_app_workspace_states(user)

    return user
