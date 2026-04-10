from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.analytics.get_metrics import get_metrics
from Delivery_app_BK.services.analytics.get_trends import get_trends
from Delivery_app_BK.services.analytics.get_breakdowns import get_breakdowns
from Delivery_app_BK.ai.tools.analytics_tools import get_analytics_snapshot


def _order(order_id: int, *, creation_date: str = "2026-03-22T12:00:00Z", state_id: int = 1, plan_id=None):
    return {
        "id": order_id,
        "creation_date": creation_date,
        "order_state_id": state_id,
        "route_plan_id": plan_id,
    }


def test_get_metrics_accumulates_paginated_orders(monkeypatch):
    pages = [
        {
            "order": [_order(1, state_id=6, plan_id=10), _order(2, state_id=7), _order(3, state_id=1)],
            "order_pagination": {"has_more": True, "next_cursor": "c2"},
        },
        {
            "order": [_order(4, state_id=6, plan_id=11), _order(5, state_id=1)],
            "order_pagination": {"has_more": False, "next_cursor": None},
        },
    ]

    call_count = {"value": 0}

    def _fake_list_orders(ctx):
        idx = call_count["value"]
        call_count["value"] += 1
        return pages[idx]

    monkeypatch.setattr("Delivery_app_BK.services.analytics._orders_window.list_orders_service", _fake_list_orders)

    result = get_metrics(ServiceContext(incoming_data={}, identity={}), "7d")

    assert result["total_orders"] == 5
    assert result["completed_orders"] == 2
    assert result["failed_orders"] == 1
    assert result["scheduled_orders"] == 2
    assert result["data_status"]["is_complete"] is True
    assert result["data_status"]["pages_fetched"] == 2


def test_get_trends_returns_all_pages(monkeypatch):
    pages = [
        {
            "order": [_order(1, creation_date="2026-03-20T08:00:00Z"), _order(2, creation_date="2026-03-20T09:00:00Z")],
            "order_pagination": {"has_more": True, "next_cursor": "c2"},
        },
        {
            "order": [_order(3, creation_date="2026-03-21T08:00:00Z")],
            "order_pagination": {"has_more": False, "next_cursor": None},
        },
    ]

    call_count = {"value": 0}

    def _fake_list_orders(ctx):
        idx = call_count["value"]
        call_count["value"] += 1
        return pages[idx]

    monkeypatch.setattr("Delivery_app_BK.services.analytics._orders_window.list_orders_service", _fake_list_orders)

    result = get_trends(ServiceContext(incoming_data={}, identity={}), "7d")

    assert result["data_status"]["is_complete"] is True
    assert result["items"] == [
        {"date": "2026-03-20", "orders_created": 2},
        {"date": "2026-03-21", "orders_created": 1},
    ]


def test_get_breakdowns_marks_truncated_when_page_cap_is_hit(monkeypatch):
    def _fake_list_orders(ctx):
        return {
            "order": [_order(1, state_id=1)],
            "order_pagination": {"has_more": True, "next_cursor": "next"},
        }

    monkeypatch.setattr("Delivery_app_BK.services.analytics._orders_window.list_orders_service", _fake_list_orders)
    monkeypatch.setattr("Delivery_app_BK.services.analytics._orders_window.MAX_ANALYTICS_PAGES", 2)

    result = get_breakdowns(ServiceContext(incoming_data={}, identity={}), "7d")

    assert result["data_status"]["is_complete"] is False
    assert "truncated" in (result["data_status"].get("warning") or "").lower()


def test_get_analytics_snapshot_aggregates_component_data_status(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_metrics",
        lambda ctx, timeframe: {
            "total_orders": 10,
            "data_status": {"is_complete": True, "pages_fetched": 1},
        },
    )
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_trends",
        lambda ctx, timeframe: {
            "items": [{"date": "2026-03-21", "orders_created": 4}],
            "data_status": {"is_complete": False, "warning": "truncated trends"},
        },
    )
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_breakdowns",
        lambda ctx, timeframe: {
            "items": [{"dimension": "scheduled_status", "values": []}],
            "data_status": {"is_complete": True, "pages_fetched": 1},
        },
    )

    result = get_analytics_snapshot(ServiceContext(incoming_data={}, identity={}), "7d")

    assert result["data_status"]["is_complete"] is False
    assert result["data_status"]["warnings"] == ["truncated trends"]
    assert result["trends"][0]["date"] == "2026-03-21"
