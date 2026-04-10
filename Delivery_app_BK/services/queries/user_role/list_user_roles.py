from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_user_roles import find_user_roles
from .serialize_user_roles import serialize_user_roles


def list_user_roles(ctx: ServiceContext):
    query = find_user_roles(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_user_roles(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "user_roles": serialized,
        "user_roles_pagination": pagination,
    }
