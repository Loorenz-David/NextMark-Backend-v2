"""
One-off backfill script to populate Order.total_weight_g, total_volume_cm3, total_item_count.
Safe to re-run (idempotent).

Usage:
  flask shell < scripts/backfill_order_totals.py
  or:
  python -c "from scripts.backfill_order_totals import run; run()"
"""
from Delivery_app_BK.models import db, Order
from sqlalchemy.orm import joinedload
from Delivery_app_BK.services.domain.order.recompute_order_totals import recompute_order_totals


def run(batch_size=500):
    offset = 0
    total = 0
    while True:
        orders = (
            db.session.query(Order)
            .options(joinedload(Order.items))
            .limit(batch_size)
            .offset(offset)
            .all()
        )
        if not orders:
            break
        for order in orders:
            recompute_order_totals(order)
        db.session.commit()
        total += len(orders)
        print(f"Backfilled {total} orders...")
        offset += batch_size
    print(f"Done. Total orders backfilled: {total}")


if __name__ == "__main__":
    run()
