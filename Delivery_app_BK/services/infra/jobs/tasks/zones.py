"""Zone background job tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from Delivery_app_BK.services.infra.jobs import with_app_context

logger = logging.getLogger(__name__)

# Orders created within this window are reassigned when a new version activates.
REASSIGNMENT_WINDOW_DAYS = 7


@with_app_context
def reassign_orders_for_new_version_job(zone_version_id: int) -> None:
    """Reassign recent orders when a new zone version is activated.

    Queries all orders within ``REASSIGNMENT_WINDOW_DAYS`` days that belong to
    the same (team_id, city_key) as the activated version and re-runs zone
    assignment for each.  Orders from other cities are skipped.
    """
    from Delivery_app_BK.models import db
    from Delivery_app_BK.models.tables.order.order import Order
    from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan
    from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
    from Delivery_app_BK.services.domain.route_operations.plan.recompute_route_group_totals import (
        recompute_route_group_totals,
    )
    from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key
    from Delivery_app_BK.zones.services.order_assignment_service import upsert_order_zone_assignment

    zone_version = db.session.get(ZoneVersion, zone_version_id)
    if zone_version is None:
        logger.warning(
            "reassign_orders_for_new_version_job: version %d not found",
            zone_version_id,
        )
        return

    team_id = zone_version.team_id
    city_key = zone_version.city_key
    cutoff = datetime.now(timezone.utc) - timedelta(days=REASSIGNMENT_WINDOW_DAYS)

    orders = (
        db.session.query(Order)
        .filter(Order.team_id == team_id, Order.creation_date >= cutoff)
        .all()
    )

    reassigned = skipped = errors = 0
    affected_plan_ids: set[int] = set()
    for order in orders:
        client_address = order.client_address or {}
        order_city_key = normalize_city_key(client_address.get("city"))
        if order_city_key != city_key:
            skipped += 1
            continue
        try:
            upsert_order_zone_assignment(
                order_id=order.id,
                team_id=team_id,
                city_key=city_key,
                client_address=client_address,
            )
            if order.route_plan_id:
                affected_plan_ids.add(order.route_plan_id)
            reassigned += 1
        except Exception:
            logger.exception("Failed to reassign order %d", order.id)
            errors += 1

    if affected_plan_ids:
        route_plans = (
            db.session.query(RoutePlan)
            .filter(RoutePlan.id.in_(affected_plan_ids), RoutePlan.team_id == team_id)
            .all()
        )
        for route_plan in route_plans:
            recompute_route_group_totals(route_plan)
        db.session.commit()

    logger.info(
        "reassign_orders_for_new_version_job: version=%d reassigned=%d skipped=%d errors=%d",
        zone_version_id,
        reassigned,
        skipped,
        errors,
    )
