"""Recompute denormalized totals on a RoutePlan from its orders. Does NOT commit."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func

from Delivery_app_BK.models import db, RoutePlan, Order

logger = logging.getLogger(__name__)


def recompute_plan_totals(plan: "RoutePlan") -> None:
    """Aggregate Order denormalized totals into plan columns. No commit issued."""
    if plan is None or plan.id is None:
        return

    result = db.session.query(
        func.sum(Order.total_weight_g),
        func.sum(Order.total_volume_cm3),
        func.sum(Order.total_item_count),
        func.count(Order.id),
    ).filter(Order.route_plan_id == plan.id).one()

    plan.total_weight_g   = float(result[0] or 0)
    plan.total_volume_cm3 = float(result[1] or 0)
    plan.total_item_count = int(result[2] or 0)
    plan.total_orders     = int(result[3] or 0)

    type_counts_rows = (
        db.session.query(Order.item_type_counts)
        .filter(
            Order.route_plan_id == plan.id,
            Order.item_type_counts.isnot(None),
        )
        .all()
    )
    merged: dict[str, int] = {}
    for (counts,) in type_counts_rows:
        if counts:
            for k, v in counts.items():
                merged[k] = merged.get(k, 0) + v
    plan.item_type_counts = {k: v for k, v in merged.items() if v >= 1} or None

    logger.debug(
        "recompute_plan_totals plan_id=%s weight=%s volume=%s items=%s orders=%s",
        plan.id,
        plan.total_weight_g,
        plan.total_volume_cm3,
        plan.total_item_count,
        plan.total_orders,
    )
