from datetime import datetime, timedelta, timezone

from Delivery_app_BK.services.domain.order.unplanned_order_retention import (
    DEFAULT_UNPLANNED_ORDER_RETENTION_DAYS,
    resolve_unplanned_order_discard_after,
)


def test_default_retention_is_five_days():
    assert DEFAULT_UNPLANNED_ORDER_RETENTION_DAYS == 5


def test_discard_after_is_now_plus_retention_days():
    now = datetime(2026, 10, 7, 12, 30, tzinfo=timezone.utc)

    assert resolve_unplanned_order_discard_after(now, 5) == now + timedelta(days=5)
