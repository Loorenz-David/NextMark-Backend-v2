from Delivery_app_BK.models import TeamInvites, db
from Delivery_app_BK.errors import NotFound, ValidationFailed

from ....context import ServiceContext
from .serialize_team_invites_received import serialize_team_invites_received


def get_team_invite_received(invite_id: int, ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to get a received invite.")

    found_invite = (
        db.session.query(TeamInvites)
        .filter(
            TeamInvites.id == invite_id,
            TeamInvites.target_user_id == ctx.user_id,
        )
        .first()
    )

    if not found_invite:
        raise NotFound(f"Team invite with id: {invite_id} does not exist.")

    serialized = serialize_team_invites_received(
        instances=[found_invite],
        ctx=ctx,
    )

    return {
        "team_invite_received": (
            serialized[0] if isinstance(serialized, list) else serialized
        )
    }
