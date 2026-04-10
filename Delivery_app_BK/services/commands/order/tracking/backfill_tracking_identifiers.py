"""
Backfill tracking identifiers for orders that were created before the
public-tracking feature was introduced.

Usage (standalone):
    cd Back_end
    python -m Delivery_app_BK.services.commands.order.tracking.backfill_tracking_identifiers

Usage (imported):
    from Delivery_app_BK.services.commands.order.tracking.backfill_tracking_identifiers import (
        backfill_tracking_identifiers,
    )
    backfill_tracking_identifiers()
"""

import sys
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

BATCH_SIZE = 100


def backfill_tracking_identifiers(batch_size: int = BATCH_SIZE) -> int:
    """Populate tracking fields for every Order that has none.

    Returns the total number of orders updated.
    """
    # Imports are deferred so that this file is safe to import without an
    # active Flask application context.
    from Delivery_app_BK.models import db, Order
    from .generate_tracking_identifiers import generate_tracking_identifiers

    logger.info("Starting tracking-identifier backfill …")

    offset = 0
    total_updated = 0

    while True:
        orders = (
            db.session.query(Order)
            .filter(Order.tracking_token_hash.is_(None))
            .order_by(Order.id)
            .limit(batch_size)
            .offset(offset)
            .all()
        )

        if not orders:
            break

        for order in orders:
            generate_tracking_identifiers(order)

        db.session.commit()
        batch_count = len(orders)
        total_updated += batch_count
        logger.info("Backfilled %d orders (running total: %d).", batch_count, total_updated)

        # If we got fewer than batch_size the query will be empty next round.
        if batch_count < batch_size:
            break

        # Keep offset at 0 — committed rows no longer match the filter.

    logger.info("Backfill complete. Total orders updated: %d.", total_updated)
    return total_updated


if __name__ == "__main__":
    # Allow running as `python -m …backfill_tracking_identifiers`
    # Requires a Flask application context to be available.
    try:
        from application import create_app  # adjust import if your factory differs
    except ImportError:
        from run import create_app  # fallback

    app = create_app()
    with app.app_context():
        updated = backfill_tracking_identifiers()
        print(f"Done. {updated} orders updated.")
