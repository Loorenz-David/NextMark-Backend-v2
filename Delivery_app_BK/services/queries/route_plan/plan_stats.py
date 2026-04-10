from typing import Type
from flask_sqlalchemy.model import Model
from sqlalchemy import func, distinct
from sqlalchemy.orm import Query

from Delivery_app_BK.models import RoutePlan, Order, Item

from ...context import ServiceContext


def plan_stats( query:Query, ctx:ServiceContext ):
    query = query.order_by(None).limit(None).offset(None)

    total_plans = query.with_entities(
        func.count( RoutePlan.id )
    ).scalar()

    state_count = (
        query
        .with_entities(
            RoutePlan.state_id,
            func.count( distinct( RoutePlan.id ) )
        )
        .group_by( RoutePlan.state_id )
        .all()
    )

    orders_count = (
        query
        .join( Order, Order.route_plan_id == RoutePlan.id )
        .with_entities( func.count( distinct( Order.id ) ) )
        .scalar()
    )

    item_count = (
        query
        .join( Order, Order.route_plan_id == RoutePlan.id )
        .join( Item, Item.order_id == Order.id )
        .with_entities( func.coalesce(func.sum(Item.quantity), 0))
        .scalar()
    )

    return {
        "plans": {
            "total": total_plans,
            "by_state": {
                state_id: count for state_id, count in state_count if state_id is not None
            }
        },
        "orders":{
            "total": orders_count
        },
        "items":{
            "total": item_count
        }
    }