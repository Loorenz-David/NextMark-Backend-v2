from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.services.context import ServiceContext
from ._orders_window import fetch_orders_for_window, timeframe_window


def get_breakdowns(ctx: ServiceContext, timeframe: str = "7d") -> dict:
    start, end = timeframe_window(timeframe)
    payload = fetch_orders_for_window(ctx, start=start, end=end, sort="date_desc")
    orders = payload["orders"]

    state_counts: dict[int, int] = defaultdict(int)
    scheduled_counts = {"scheduled": 0, "unscheduled": 0}

    for order in orders:
        state_id = order.get("order_state_id")
        if state_id is not None:
            state_counts[int(state_id)] += 1

        if order.get("route_plan_id") is None:
            scheduled_counts["unscheduled"] += 1
        else:
            scheduled_counts["scheduled"] += 1

    breakdowns: list[dict] = [
        {
            "dimension": "scheduled_status",
            "values": [
                {"label": "scheduled", "count": scheduled_counts["scheduled"]},
                {"label": "unscheduled", "count": scheduled_counts["unscheduled"]},
            ],
        },
        {
            "dimension": "order_state_id",
            "values": [
                {"label": str(state_id), "count": count}
                for state_id, count in sorted(state_counts.items())
            ],
        },
    ]

    return {
        "items": breakdowns,
        "data_status": payload["data_status"],
    }
