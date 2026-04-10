from Delivery_app_BK.errors import NotFound, PermissionDenied, ValidationFailed
from Delivery_app_BK.models import db, TeamInvites, User
from Delivery_app_BK.services.commands.auth.token_utils import build_user_tokens
from Delivery_app_BK.services.domain.user import (
    has_team_workspace_snapshot,
    is_team_workspace_active,
    set_app_current_workspace,
    sync_all_app_workspace_states,
)
from ...context import ServiceContext


def accept_team_invitation(ctx: ServiceContext, invitation_id: int):
    if invitation_id is None:
        raise ValidationFailed("Invitation id is required to accept an invitation.")
    if not ctx.user_id:
        raise ValidationFailed("User id is required to accept an invitation.")

    invite = db.session.get(TeamInvites, invitation_id)
    
    if not invite:
        raise NotFound(f"Team invitation with id '{invitation_id}' was not found.")

    if invite.target_user_id != ctx.user_id:
        raise PermissionDenied(
            "You are not authorized to accept this team invitation."
        )

    user = db.session.get(User, ctx.user_id)
    if not user:
        raise NotFound("User was not found for invitation acceptance.")

    if has_team_workspace_snapshot(user) or is_team_workspace_active(user):
        raise ValidationFailed(
            "You cannot accept a team invitation while already belonging to another team."
        )

    user.team_id = invite.team_id
    user.user_role_id = invite.user_role_id
    user.team_workspace_team_id = None
    user.team_workspace_role_id = None
    sync_all_app_workspace_states(user)
    if ctx.app_scope:
        set_app_current_workspace(user, ctx.app_scope, "team")

    db.session.delete(invite)
    tokens = build_user_tokens(
        user,
        app_scope=ctx.app_scope or "admin",
        session_scope_id=ctx.session_scope_id,
        time_zone=ctx.identity.get("time_zone"),
    )
    db.session.commit()
    db.session.refresh(user)
    return tokens
