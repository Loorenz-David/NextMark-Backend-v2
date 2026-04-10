from __future__ import annotations

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from ._orders_window import fetch_orders_for_window, timeframe_window


def get_metrics(ctx: ServiceContext, timeframe: str = "7d") -> dict:
    start, end = timeframe_window(timeframe)
    payload = fetch_orders_for_window(ctx, start=start, end=end, sort="date_desc")
    orders = payload["orders"]

    total_orders = len(orders)
    scheduled_orders = sum(1 for order in orders if order.get("route_plan_id") is not None)
    completed_orders = sum(1 for order in orders if order.get("order_state_id") == OrderStateId.COMPLETED)
    failed_orders = sum(1 for order in orders if order.get("order_state_id") == OrderStateId.FAIL)

    completion_rate = (completed_orders / total_orders) if total_orders else 0.0
    scheduled_rate = (scheduled_orders / total_orders) if total_orders else 0.0

    return {
        "timeframe": timeframe,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "total_orders": total_orders,
        "scheduled_orders": scheduled_orders,
        "unscheduled_orders": max(total_orders - scheduled_orders, 0),
        "completed_orders": completed_orders,
        "failed_orders": failed_orders,
        "completion_rate": round(completion_rate, 4),
        "scheduled_rate": round(scheduled_rate, 4),
        "data_status": payload["data_status"],
    }
