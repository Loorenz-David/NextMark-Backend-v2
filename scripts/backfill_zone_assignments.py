"""Backfill zone assignments for orders missing an OrderZoneAssignment record.

Usage
-----
    # Process orders from the last 365 days (default):
    python scripts/backfill_zone_assignments.py

    # Process orders from the last 90 days:
    python scripts/backfill_zone_assignments.py --days-back 90

    # Process ALL historical orders regardless of creation date:
    python scripts/backfill_zone_assignments.py --all

    # Target a specific environment:
    python scripts/backfill_zone_assignments.py --days-back 365 --env production
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from Delivery_app_BK import create_app
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.order.order import Order
from Delivery_app_BK.models.tables.zones.order_zone_assignment import OrderZoneAssignment
from Delivery_app_BK.zones.services.order_assignment_service import upsert_order_zone_assignment

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill_zone_assignments(days_back: int | None = 365) -> dict:
    """Upsert zone assignments for every order that has no existing row.

    Uses a LEFT JOIN to find unassigned orders efficiently.  Pass
    ``days_back=None`` to process the entire order history.

    Returns a summary dict with keys: total_candidates, processed,
    assigned, unassigned, errors.
    """
    q = (
        db.session.query(Order)
        .outerjoin(OrderZoneAssignment, OrderZoneAssignment.order_id == Order.id)
        .filter(OrderZoneAssignment.id.is_(None))
    )
    if days_back is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        q = q.filter(Order.creation_date >= cutoff)

    orders = q.all()
    logger.info("Found %d orders without zone assignments", len(orders))

    processed = assigned = unassigned = errors = 0
    for order in orders:
        client_address = order.client_address or {}
        try:
            _, action = upsert_order_zone_assignment(
                order_id=order.id,
                team_id=order.team_id,
                client_address=client_address,
            )
            processed += 1
            if action == "unassigned":
                unassigned += 1
            else:
                assigned += 1
        except Exception as exc:
            logger.error("Failed to assign order %d: %s", order.id, exc)
            errors += 1

    return {
        "total_candidates": len(orders),
        "processed": processed,
        "assigned": assigned,
        "unassigned": unassigned,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill zone assignments for orders that are missing one",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="Process orders created within this many days (default: 365)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all orders regardless of creation date (overrides --days-back)",
    )
    parser.add_argument("--env", type=str, default="development")
    args = parser.parse_args()

    app = create_app(args.env)
    with app.app_context():
        result = backfill_zone_assignments(days_back=None if args.all else args.days_back)
        print({"status": "ok", **result})


if __name__ == "__main__":
    main()
