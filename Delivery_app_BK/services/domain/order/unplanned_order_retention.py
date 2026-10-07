"""
Retention rule for unplanned orders.

An order ingested without a plan objective (Shopify "customer took it") is
kept so staff can correct a cashier mistake. If it is still unplanned once
its discard_after passes, it carries no value to the app and may be purged.
"""

from __future__ import annotations

from datetime import datetime, timedelta

DEFAULT_UNPLANNED_ORDER_RETENTION_DAYS = 5


def resolve_unplanned_order_discard_after(now: datetime, retention_days: int) -> datetime:
    return now + timedelta(days=retention_days)
