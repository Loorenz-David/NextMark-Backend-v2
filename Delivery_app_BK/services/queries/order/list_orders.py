from sqlalchemy import false

from Delivery_app_BK.models import Order, OrderZoneAssignment, RouteGroup, db
from sqlalchemy.orm import selectinload

from ..utils import build_opaque_pagination
from ...context import ServiceContext
from .find_orders import find_orders
from .serialize_order import serialize_orders
from .order_stats import order_stats

MAX_ORDER_LIMIT = 200


def list_orders(
    ctx: ServiceContext,
    plan_id: int | None = None,
    route_plan_id: int | None = None,
    route_group_id: int | None = None,
):
    
    base_query = db.session.query(Order).options(
        selectinload(Order.delivery_windows),
        selectinload(Order.items),
    )
    effective_route_plan_id = route_plan_id
    if effective_route_plan_id is None:
        effective_route_plan_id = plan_id
    if effective_route_plan_id is not None:
        base_query = base_query.filter(
            Order.route_plan_id == effective_route_plan_id
        )

    if route_group_id is not None:
        route_group = db.session.get(RouteGroup, route_group_id)
        if (
            route_group is None
            or route_group.team_id != ctx.team_id
            or (effective_route_plan_id is not None and route_group.route_plan_id != effective_route_plan_id)
        ):
            base_query = base_query.filter(false())
        elif route_group.zone_id is None:
            # No-Zone groups can now be created multiple times inside a plan,
            # so filtering must be explicit by route_group_id.
            base_query = base_query.filter(Order.route_group_id == route_group.id)
        else:
            base_query = base_query.join(
                OrderZoneAssignment,
                OrderZoneAssignment.order_id == Order.id,
            ).filter(
                OrderZoneAssignment.zone_id == route_group.zone_id,
                OrderZoneAssignment.is_unassigned.is_(False),
            )

    query = find_orders(ctx.query_params, ctx, query=base_query)
    stats_query_params = {
        key: value
        for key, value in dict(ctx.query_params).items()
        if key not in {"after_cursor", "before_cursor", "limit"}
    }
    stats_query = find_orders(stats_query_params, ctx, query=base_query)

    limit = min(int(ctx.query_params.get("limit", MAX_ORDER_LIMIT)), MAX_ORDER_LIMIT)
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit

    page_instances = results[ :limit ]

    pagination = build_opaque_pagination(
        page_instances = page_instances, 
        has_more = has_more, 
        date_attr = 'creation_date',
        id_attr = 'id',
    )
    

    serialize_objects = serialize_orders( 
        instances = page_instances,
        ctx = ctx
    )

    stats = order_stats( 
        query = stats_query, 
        ctx = ctx
    )

    return {
        "order": serialize_objects,
        "order_stats": stats,
        "order_pagination": pagination
    }
