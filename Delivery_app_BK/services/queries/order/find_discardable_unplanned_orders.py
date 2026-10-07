from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from Delivery_app_BK.models import Order, db


def find_discardable_unplanned_orders(now: datetime, limit: int) -> dict[int, list[int]]:
    """Order ids, grouped by team, whose discard_after has passed while they
    are still unplanned (no objective, no plan, no route group)."""
    rows = (
        db.session.query(Order.team_id, Order.id)
        .filter(
            Order.discard_after.isnot(None),
            Order.discard_after <= now,
            Order.order_plan_objective.is_(None),
            Order.route_plan_id.is_(None),
            Order.route_group_id.is_(None),
        )
        .order_by(Order.discard_after.asc(), Order.id.asc())
        .limit(limit)
        .all()
    )

    order_ids_by_team: dict[int, list[int]] = defaultdict(list)
    for team_id, order_id in rows:
        order_ids_by_team[team_id].append(order_id)
    return dict(order_ids_by_team)
