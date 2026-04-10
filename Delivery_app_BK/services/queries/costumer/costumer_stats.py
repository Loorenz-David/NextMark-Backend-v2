from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Query

from Delivery_app_BK.models import Costumer, Order, db

from ...context import ServiceContext


def costumer_stats(ctx: ServiceContext, base_query: Query | None = None) -> dict:
    query = base_query or db.session.query(Costumer)
    base_query_no_page = query.order_by(None).limit(None).offset(None)

    costumer_ids_subq = (
        base_query_no_page.with_entities(Costumer.id.label("id")).distinct().subquery()
    )

    total_costumers = db.session.query(func.count()).select_from(costumer_ids_subq).scalar() or 0

    with_orders = (
        db.session.query(func.count(func.distinct(Order.costumer_id)))
        .join(costumer_ids_subq, Order.costumer_id == costumer_ids_subq.c.id)
        .filter(Order.costumer_id.isnot(None))
        .scalar()
        or 0
    )

    without_orders = max(int(total_costumers) - int(with_orders), 0)

    return {
        "total_costumers": int(total_costumers),
        "total_with_orders": int(with_orders),
        "total_without_orders": int(without_orders),
    }

