from typing import Iterable

from Delivery_app_BK.models import Item, Order, RoutePlan


def calculate_item_totals(items: Iterable[Item]) -> dict:
    total_items = 0
    total_volume = 0.0
    total_weight = 0.0

    for item in items:
        quantity = item.quantity or 1
        total_items += quantity
        total_volume += _item_volume_cm3(item) * quantity
        total_weight += _item_weight_g(item) * quantity

    return {
        "total_items": total_items,
        "total_volume": total_volume,
        "total_weight": total_weight,
    }


def calculate_order_metrics(order: Order) -> dict:
    items = getattr(order, "items", None) or []
    return calculate_item_totals(items)


def calculate_plan_metrics(plan: RoutePlan) -> dict:
    orders = getattr(plan, "orders", None) or []
    items = []
    for order in orders:
        items.extend(getattr(order, "items", None) or [])

    metrics = calculate_item_totals(items)
    metrics["total_orders"] = len(orders)
    return metrics


def _item_volume_cm3(item: Item) -> float:
    depth = _to_float(getattr(item, "dimension_depth", None))
    height = _to_float(getattr(item, "dimension_height", None))
    width = _to_float(getattr(item, "dimension_width", None))
    if not depth or not height or not width:
        return 0.0
    return depth * height * width


def _item_weight_g(item: Item) -> float:
    weight = _to_float(getattr(item, "weight", None))
    if not weight:
        return 0.0
    return weight


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
