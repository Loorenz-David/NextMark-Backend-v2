from datetime import datetime, timezone

from Delivery_app_BK.models import Order


def touch_order_items_updated_at(order: Order | None) -> None:
    if order is None:
        return
    order.items_updated_at = datetime.now(timezone.utc)


def touch_orders_items_updated_at(orders: list[Order]) -> None:
    now = datetime.now(timezone.utc)
    for order in orders:
        if order is None:
            continue
        order.items_updated_at = now
