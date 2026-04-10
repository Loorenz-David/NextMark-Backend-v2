from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db, User
from sqlalchemy import or_

from ...context import ServiceContext
from Delivery_app_BK.services.commands.auth.token_utils import build_user_tokens
from Delivery_app_BK.services.domain.user import (
    get_team_workspace_assignment,
    set_app_current_workspace,
    sync_all_app_workspace_states,
)


def leave_team(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to leave a team.")

    user = db.session.get(User, ctx.user_id)
    if not user:
        raise NotFound("User was not found.")

    if user.primals_team_id is None or user.primals_role_id is None:
        raise ValidationFailed("No primal team or role to return to.")

    membership_team_id, membership_role_id = get_team_workspace_assignment(user)

    if membership_team_id is None or membership_role_id is None:
        raise ValidationFailed("You do not currently belong to a team.")

    team_members = (
        db.session.query(User)
        .filter(
            or_(
                User.team_id == membership_team_id,
                User.team_workspace_team_id == membership_team_id,
            )
        )
        .count()
    )
    if team_members <= 1:
        raise ValidationFailed("You cannot leave a team with only one member.")

    if user.team_id == membership_team_id and user.user_role_id == membership_role_id:
        user.team_id = user.primals_team_id
        user.user_role_id = user.primals_role_id

    if user.team_workspace_team_id == membership_team_id:
        user.team_workspace_team_id = None
        user.team_workspace_role_id = None

    set_app_current_workspace(user, "admin", "personal")
    set_app_current_workspace(user, "driver", "personal")
    sync_all_app_workspace_states(user)

    db.session.commit()

    return build_user_tokens(
        user,
        app_scope=ctx.app_scope or "admin",
        session_scope_id=ctx.session_scope_id,
        time_zone=ctx.identity.get("time_zone"),
    )
