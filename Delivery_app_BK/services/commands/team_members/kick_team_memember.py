from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, User
from sqlalchemy import or_

from ...context import ServiceContext
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.services.domain.user import (
    resolve_user_team_membership,
    set_app_current_workspace,
    sync_all_app_workspace_states,
)


# missing to configure invalidating token when a user gets kicked out.

def kick_team_memember(ctx: ServiceContext, user_id: int):
    if not user_id:
        raise ValidationFailed("User id is required to remove a team member.")

    user = db.session.get(User, user_id)
    if not user:
        raise NotFound(f"User with id '{user_id}' was not found.")
    membership = resolve_user_team_membership(user, ctx.team_id)
    if not membership["is_member"]:
        raise ValidationFailed("User does not belong to this team.")

    if user.primals_team_id is None or user.primals_role_id is None:
        raise ValidationFailed("User has no primal team or role to return to.")

    team_members = (
        db.session.query(User)
        .filter(
            or_(
                User.team_id == ctx.team_id,
                User.team_workspace_team_id == ctx.team_id,
            )
        )
        .count()
    )
    if team_members <= 1:
        raise ValidationFailed("You cannot remove the only team member.")

    if membership["is_active_workspace"]:
        user.team_id = user.primals_team_id
        user.user_role_id = user.primals_role_id

    if user.team_workspace_team_id == ctx.team_id:
        user.team_workspace_team_id = None
        user.team_workspace_role_id = None

    set_app_current_workspace(user, "admin", "personal")
    set_app_current_workspace(user, "driver", "personal")
    sync_all_app_workspace_states(user)

    db.session.commit()
    return user
