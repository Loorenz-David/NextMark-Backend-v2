from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.services.context import ServiceContext
from ._orders_window import fetch_orders_for_window, timeframe_window


def get_trends(ctx: ServiceContext, timeframe: str = "7d") -> dict:
    start, end = timeframe_window(timeframe)
    payload = fetch_orders_for_window(ctx, start=start, end=end, sort="date_asc")
    orders = payload["orders"]

    buckets: dict[str, int] = defaultdict(int)
    for order in orders:
        creation_date = order.get("creation_date")
        if not creation_date:
            continue
        day = str(creation_date)[:10]
        if day:
            buckets[day] += 1

    return {
        "items": [
            {"date": day, "orders_created": buckets[day]}
            for day in sorted(buckets.keys())
        ],
        "data_status": payload["data_status"],
    }
