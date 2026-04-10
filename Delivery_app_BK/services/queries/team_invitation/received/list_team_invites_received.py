from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import TeamInvites, db

from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_team_invites_received import find_team_invites_received
from .serialize_team_invites_received import serialize_team_invites_received


def list_team_invites_received(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to list received invites.")

    base_query = db.session.query(TeamInvites).filter(
        TeamInvites.target_user_id == ctx.user_id
    )

    query = find_team_invites_received(
        ctx.query_params,
        ctx,
        query=base_query,
    )

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_team_invites_received(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "team_invites_received": serialized,
        "team_invites_received_pagination": pagination,
    }
