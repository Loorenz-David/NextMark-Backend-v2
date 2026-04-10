from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import TeamInvites, db

from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_team_invites_sent import find_team_invites_sent
from .serialize_team_invites_sent import serialize_team_invites_sent


def list_team_invites_sent(ctx: ServiceContext):
    if not ctx.team_id:
        raise ValidationFailed("Team id is required to list sent invites.")

    base_query = db.session.query(TeamInvites).filter(
        TeamInvites.team_id == ctx.team_id
    )

    query = find_team_invites_sent(ctx.query_params, ctx, query=base_query)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_team_invites_sent(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "team_invites_sent": serialized,
        "team_invites_sent_pagination": pagination,
    }
