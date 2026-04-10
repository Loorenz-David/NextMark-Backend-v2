from Delivery_app_BK.errors import NotFound, PermissionDenied, ValidationFailed
from Delivery_app_BK.models import db, TeamInvites
from ...context import ServiceContext


def delete_team_invitation(ctx: ServiceContext, invitation_id: int):
    if invitation_id is None:
        raise ValidationFailed("Invitation id is required to delete an invitation.")

    invite = db.session.get(TeamInvites, invitation_id)
    if not invite:
        raise NotFound(f"Team invitation with id '{invitation_id}' was not found.")

    if invite.team_id != ctx.team_id and invite.target_user_id != ctx.user_id:
        raise PermissionDenied(
            "You are not authorized to delete this team invitation."
        )

    db.session.delete(invite)
    db.session.commit()
    return invite
