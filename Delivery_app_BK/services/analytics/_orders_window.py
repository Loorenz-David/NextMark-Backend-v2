from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.order.list_orders import list_orders as list_orders_service

MAX_ANALYTICS_PAGE_LIMIT = 200
MAX_ANALYTICS_PAGES = 100


def timeframe_window(timeframe: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    normalized = (timeframe or "7d").strip().lower()
    if normalized == "24h":
        return now - timedelta(hours=24), now
    if normalized == "30d":
        return now - timedelta(days=30), now
    return now - timedelta(days=7), now


def fetch_orders_for_window(
    ctx: ServiceContext,
    *,
    start: datetime,
    end: datetime,
    sort: str,
) -> dict:
    """Fetch all orders in a timeframe using deterministic cursor pagination."""
    all_orders: list[dict] = []
    after_cursor: str | None = None
    pages = 0
    truncated = False

    while True:
        pages += 1
        query_params = {
            "creation_date_from": start.isoformat(),
            "creation_date_to": end.isoformat(),
            "limit": MAX_ANALYTICS_PAGE_LIMIT,
            "sort": sort,
        }
        if after_cursor:
            query_params["after_cursor"] = after_cursor

        query_ctx = ServiceContext(
            incoming_data=ctx.incoming_data,
            identity=ctx.identity,
            on_query_return="list",
            query_params=query_params,
        )
        payload = list_orders_service(query_ctx)
        orders = payload.get("order") or []
        all_orders.extend(orders)

        pagination = payload.get("order_pagination") or {}
        has_more = bool(pagination.get("has_more"))
        if not has_more:
            break

        after_cursor = pagination.get("next_cursor")
        if not after_cursor or pages >= MAX_ANALYTICS_PAGES:
            truncated = True
            break

    status = {
        "is_complete": not truncated,
        "pages_fetched": pages,
        "row_count": len(all_orders),
        "max_pages": MAX_ANALYTICS_PAGES,
        "page_limit": MAX_ANALYTICS_PAGE_LIMIT,
    }
    if truncated:
        status["warning"] = (
            "Analytics results truncated due to page cap. "
            f"Fetched {pages} pages with limit {MAX_ANALYTICS_PAGE_LIMIT}."
        )

    return {
        "orders": all_orders,
        "data_status": status,
    }
