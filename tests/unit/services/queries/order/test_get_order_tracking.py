from types import SimpleNamespace

from Delivery_app_BK.services.queries.order import get_order_tracking as module


class QueryStub:
    def __init__(self, order):
        self.order = order
        self.filters = []

    def filter(self, *filters):
        self.filters.extend(filters)
        return self

    def first(self):
        return self.order


def test_get_order_tracking_returns_public_order_references(monkeypatch):
    captured = {}
    order = SimpleNamespace(
        tracking_number="TRK-101",
        order_scalar_id=101,
        reference_number="REF-101",
        external_source="shopify",
        events=[],
        state=None,
        team=SimpleNamespace(name="Demo Team", time_zone="Europe/Stockholm"),
        delivery_windows=[],
    )

    def fake_query(model):
        captured["model"] = model
        query = QueryStub(order)
        captured["query"] = query
        return query

    monkeypatch.setattr(module.db.session, "query", fake_query)

    result = module.get_order_tracking("raw-token")

    assert captured["model"] is module.Order
    assert captured["query"].filters
    assert result["tracking_number"] == "TRK-101"
    assert result["order_scalar_id"] == 101
    assert result["reference_number"] == "REF-101"
    assert result["external_source"] == "shopify"
    assert result["team_name"] == "Demo Team"
