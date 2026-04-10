from Delivery_app_BK.models import RoutePlan
from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.requests.route_plan.plan.list_route_plans import (
    parse_list_route_plans_query,
)

from ..utils import build_opaque_pagination
from ...context import ServiceContext
from .find_plans import find_plans
from .serialize_plan import serialize_plans
from .plan_stats import plan_stats


def list_route_plans(ctx: ServiceContext):
    params = parse_list_route_plans_query(
        query_params=ctx.query_params,
        incoming_data=ctx.incoming_data,
    )

    query = find_plans(params, ctx).options(selectinload(RoutePlan.route_groups))
    stats_query_params = {
        key: value
        for key, value in dict(params).items()
        if key not in {"after_cursor", "before_cursor", "limit"}
    }
    stats_query = find_plans(stats_query_params, ctx)

    limit = min(int(params.get("limit", MAX_PLAN_LIMIT)), MAX_PLAN_LIMIT)
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit

    page_instances = results[:limit]

    pagination = build_opaque_pagination(
        page_instances=page_instances,
        has_more=has_more,
        date_attr="created_at",
        id_attr="id",
    )

    serialize_objects = serialize_plans(
        instances=page_instances,
        ctx=ctx,
    )

    stats = plan_stats(
        query=stats_query,
        ctx=ctx,
    )

    return {
        "route_plan": serialize_objects,
        "route_plan_stats": stats,
        "route_plan_pagination": pagination,
    }


MAX_PLAN_LIMIT = 25