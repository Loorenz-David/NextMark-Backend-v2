from Delivery_app_BK.models import TeamInvites
from Delivery_app_BK.errors import NotFound

from ....context import ServiceContext
from ...get_instance import get_instance
from .serialize_team_invites_sent import serialize_team_invites_sent


def get_team_invite_sent(invite_id: int, ctx: ServiceContext):
    found_invite = get_instance(
        ctx=ctx,
        model=TeamInvites,
        value=invite_id,
    )

    if not found_invite:
        raise NotFound(f"Team invite with id: {invite_id} does not exist.")

    serialized = serialize_team_invites_sent(
        instances=[found_invite],
        ctx=ctx,
    )

    return {
        "team_invite_sent": (
            serialized[0] if isinstance(serialized, list) else serialized
        )
    }
