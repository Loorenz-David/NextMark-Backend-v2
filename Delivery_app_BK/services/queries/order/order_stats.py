from sqlalchemy import func
from sqlalchemy.orm import Query
from Delivery_app_BK.models import Order, Item, db
from ...context import ServiceContext


def order_stats(query: Query, ctx: ServiceContext):
    # --------------------------------------------------
    # Remove ordering & pagination (stats must ignore it)
    # --------------------------------------------------
    base_query = query.order_by(None).limit(None).offset(None)

    # --------------------------------------------------
    # Build DISTINCT order id subquery (safeguard joins)
    # --------------------------------------------------
    order_ids_subq = base_query.with_entities(Order.id.label("id")).distinct().subquery()

    # --------------------------------------------------
    # Total orders
    # --------------------------------------------------
    total_orders = (
        db.session.query(func.count())
        .select_from(order_ids_subq)
        .scalar()
    )

    # --------------------------------------------------
    # Orders grouped by state
    # --------------------------------------------------
    state_count = (
        db.session.query(
            Order.order_state_id,
            func.count()
        )
        .join(order_ids_subq, Order.id == order_ids_subq.c.id)
        .group_by(Order.order_state_id)
        .all()
    )

    # --------------------------------------------------
    # Total item quantity (safe from duplicate joins)
    # --------------------------------------------------
    item_count = (
        db.session.query(func.coalesce(func.sum(Item.quantity), 0))
        .join(order_ids_subq, Item.order_id == order_ids_subq.c.id)
        .scalar()
    )

    return {
        "orders": {
            "total": total_orders,
            "by_state": {
                state_id: count
                for state_id, count in state_count
                if state_id is not None
            },
        },
        "items": {
            "total": item_count
        },
    }
