from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_team_members import find_team_members
from .serialize_team_members import serialize_team_members


def list_team_members(ctx: ServiceContext):
    query = find_team_members(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_team_members(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "team_members": serialized,
        "team_members_pagination": pagination,
    }
