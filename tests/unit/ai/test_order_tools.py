import pytest

from Delivery_app_BK.ai.tools import order_tools as module


class _DummyCtx:
    def __init__(self):
        self.query_params = {}


def test_list_orders_tool_parses_weight_eq_filter_from_q(monkeypatch):
    captured = {}

    def _fake_list_orders_service(ctx, plan_id=None):
        captured["plan_id"] = plan_id
        captured["query_params"] = dict(ctx.query_params)
        return {"orders": []}

    monkeypatch.setattr(module, "list_orders_service", _fake_list_orders_service)

    ctx = _DummyCtx()
    module.list_orders_tool(ctx, q="weight=1kg")

    assert captured["plan_id"] is None
    assert captured["query_params"]["total_weight_eq_g"] == pytest.approx(1000.0)
    assert "q" not in captured["query_params"]


def test_list_orders_tool_parses_volume_filter_and_keeps_remaining_query(monkeypatch):
    captured = {}

    def _fake_list_orders_service(ctx, plan_id=None):
        captured["query_params"] = dict(ctx.query_params)
        return {"orders": []}

    monkeypatch.setattr(module, "list_orders_service", _fake_list_orders_service)

    ctx = _DummyCtx()
    module.list_orders_tool(ctx, q="fragile volume>=2l in stockholm")

    assert captured["query_params"]["total_volume_min_cm3"] == pytest.approx(2000.0)
    assert captured["query_params"]["q"] == "fragile in stockholm"


def test_list_orders_tool_forwards_explicit_numeric_filters(monkeypatch):
    captured = {}

    def _fake_list_orders_service(ctx, plan_id=None):
        captured["query_params"] = dict(ctx.query_params)
        return {"orders": []}

    monkeypatch.setattr(module, "list_orders_service", _fake_list_orders_service)

    ctx = _DummyCtx()
    module.list_orders_tool(
        ctx,
        total_weight_min_g=500.0,
        total_weight_max_g=1500.0,
        total_volume_eq_cm3=2500.0,
    )

    assert captured["query_params"]["total_weight_min_g"] == pytest.approx(500.0)
    assert captured["query_params"]["total_weight_max_g"] == pytest.approx(1500.0)
    assert captured["query_params"]["total_volume_eq_cm3"] == pytest.approx(2500.0)
