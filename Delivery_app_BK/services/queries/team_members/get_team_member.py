from Delivery_app_BK.models import User, db
from Delivery_app_BK.errors import NotFound
from sqlalchemy import or_

from ...context import ServiceContext
from .serialize_team_members import serialize_team_members


def get_team_member(user_id: int, ctx: ServiceContext):
    query = db.session.query(User).filter(User.id == user_id)

    if ctx.team_id:
        query = query.filter(
            or_(
                User.team_id == ctx.team_id,
                User.team_workspace_team_id == ctx.team_id,
            )
        )

    found_user = query.first()

    if not found_user:
        raise NotFound(f"User with id: {user_id} does not exist.")

    serialized = serialize_team_members(
        instances=[found_user],
        ctx=ctx,
    )

    return {
        "team_member": serialized[0] if isinstance(serialized, list) else serialized
    }
