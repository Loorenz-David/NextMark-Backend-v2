from Delivery_app_BK.models import Order
from Delivery_app_BK.services.queries.utils.metrics import calculate_item_totals


def recompute_order_totals(order: Order) -> None:
    """Recompute denormalized totals from in-memory order.items. Does NOT commit."""
    items = list(getattr(order, "items", None) or [])
    totals = calculate_item_totals(items)
    order.total_weight_g = totals["total_weight"]
    order.total_volume_cm3 = totals["total_volume"]
    order.total_item_count = totals["total_items"]

    merged: dict[str, int] = {}
    for item in items:
        item_type = getattr(item, "item_type", None)
        if not item_type:
            continue
        quantity = int(getattr(item, "quantity", None) or 1)
        merged[item_type] = merged.get(item_type, 0) + quantity
    order.item_type_counts = {k: v for k, v in merged.items() if v >= 1} or None
