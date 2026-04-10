import importlib
from types import SimpleNamespace

module = importlib.import_module("Delivery_app_BK.services.queries.order.list_orders")


class _DummyQuery:
    def __init__(self):
        self.ops: list[str] = []
        self.filter_calls = 0

    def options(self, *args, **kwargs):
        self.ops.append("options")
        return self

    def filter(self, *args, **kwargs):
        self.ops.append("filter")
        self.filter_calls += 1
        return self

    def join(self, *args, **kwargs):
        self.ops.append("join")
        return self

    def outerjoin(self, *args, **kwargs):
        self.ops.append("outerjoin")
        return self

    def limit(self, *_args, **_kwargs):
        self.ops.append("limit")
        return self

    def all(self):
        return []


def _patch_common(monkeypatch, query_obj):
    monkeypatch.setattr(module.db.session, "query", lambda model: query_obj)
    monkeypatch.setattr(module, "find_orders", lambda *_args, **kwargs: kwargs["query"])
    monkeypatch.setattr(module, "serialize_orders", lambda **_kwargs: [])
    monkeypatch.setattr(module, "order_stats", lambda **_kwargs: {})
    monkeypatch.setattr(module, "build_opaque_pagination", lambda **_kwargs: {})


def test_list_orders_no_zone_group_filters_by_route_group_id(monkeypatch):
    query = _DummyQuery()
    _patch_common(monkeypatch, query)
    monkeypatch.setattr(
        module.db.session,
        "get",
        lambda model, pk: SimpleNamespace(id=pk, team_id=1, route_plan_id=42, zone_id=None),
    )

    ctx = SimpleNamespace(team_id=1, query_params={})
    module.list_orders(ctx, route_plan_id=42, route_group_id=10)

    assert "outerjoin" not in query.ops
    assert "join" not in query.ops


def test_list_orders_zone_group_uses_join_assigned_filter(monkeypatch):
    query = _DummyQuery()
    _patch_common(monkeypatch, query)
    monkeypatch.setattr(
        module.db.session,
        "get",
        lambda model, pk: SimpleNamespace(id=pk, team_id=1, route_plan_id=42, zone_id=7),
    )

    ctx = SimpleNamespace(team_id=1, query_params={})
    module.list_orders(ctx, route_plan_id=42, route_group_id=10)

    assert "join" in query.ops
    assert "outerjoin" not in query.ops


def test_list_orders_cross_plan_group_is_rejected(monkeypatch):
    query = _DummyQuery()
    _patch_common(monkeypatch, query)
    monkeypatch.setattr(
        module.db.session,
        "get",
        lambda model, pk: SimpleNamespace(id=pk, team_id=1, route_plan_id=99, zone_id=7),
    )

    ctx = SimpleNamespace(team_id=1, query_params={})
    module.list_orders(ctx, route_plan_id=42, route_group_id=10)

    assert "join" not in query.ops
    assert "outerjoin" not in query.ops
    assert query.filter_calls >= 2
