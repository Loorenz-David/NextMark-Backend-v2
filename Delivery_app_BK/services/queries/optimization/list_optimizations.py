from Delivery_app_BK.models import db, RouteSolution
from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_optimizations import find_optimizations
from .serialize_optimizations import serialize_optimizations


def list_optimizations(route_group_id: int, ctx: ServiceContext):
    if not isinstance(route_group_id, int):
        raise ValidationFailed("route_group_id must be an integer.")

    base_query = db.session.query(RouteSolution).filter(
        RouteSolution.route_group_id == route_group_id
    )

    query = find_optimizations(
        params=ctx.query_params,
        ctx=ctx,
        query=base_query,
    )

    limit = int(ctx.query_params.get("limit", 10))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_optimizations(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "optimizations": serialized,
        "optimizations_pagination": pagination,
    }
