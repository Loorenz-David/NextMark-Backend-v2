from __future__ import annotations

from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import Order, db

from ...context import ServiceContext
from ..order.serialize_order import serialize_orders


def list_costumer_orders(costumer_id: int, ctx: ServiceContext):
    query = db.session.query(Order).options(selectinload(Order.delivery_windows))

    if ctx.team_id:
        query = query.filter(Order.team_id == ctx.team_id)

    limit = int(ctx.query_params.get("limit", 50))
    limit = max(1, min(limit, 200))
    offset = int(ctx.query_params.get("offset", 0))
    offset = max(0, offset)

    instances = (
        query.filter(
            Order.costumer_id == costumer_id,
            Order.archive_at.is_(None),
        )
        .order_by(Order.creation_date.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "order": serialize_orders(instances=instances, ctx=ctx),
    }
