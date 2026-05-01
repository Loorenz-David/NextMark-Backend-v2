import importlib
from types import SimpleNamespace


module = importlib.import_module("Delivery_app_BK.services.queries.order.find_orders")


class _DummyQuery:
    def __init__(self):
        self.filter_calls = 0
        self.order_by_calls = 0

    def filter(self, *_args, **_kwargs):
        self.filter_calls += 1
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        self.order_by_calls += 1
        return self

    def distinct(self):
        return self


class _StateIdQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)

    def exists(self):
        return False


def _ctx():
    return SimpleNamespace(inject_team_id=False, query_params={})


def test_find_orders_accepts_order_state_names(monkeypatch):
    query = _DummyQuery()
    state_queries = []

    def _query(model):
        state_queries.append(model)
        return _StateIdQuery([(8,)])

    monkeypatch.setattr(module.db.session, "query", _query)
    monkeypatch.setattr(module, "apply_opaque_pagination_by_date", lambda **kwargs: kwargs["query"])

    result = module.find_orders({"order_state": "Fail"}, _ctx(), query=query)

    assert result is query
    assert query.filter_calls >= 2
    assert state_queries == [module.OrderState.id]


def test_find_orders_rejects_unknown_order_state_names(monkeypatch):
    query = _DummyQuery()

    monkeypatch.setattr(module.db.session, "query", lambda _model: _StateIdQuery([]))
    monkeypatch.setattr(module, "apply_opaque_pagination_by_date", lambda **kwargs: kwargs["query"])

    result = module.find_orders({"order_state": ["MissingState"]}, _ctx(), query=query)

    assert result is query
    assert query.filter_calls >= 2


def test_find_orders_accepts_order_schedule_from_alias(monkeypatch):
    query = _DummyQuery()
    state_queries = []

    def _query(model):
        state_queries.append(model)
        return _StateIdQuery([])

    to_datetime_calls = []

    monkeypatch.setattr(module.db.session, "query", _query)
    monkeypatch.setattr(module, "to_datetime", lambda value: to_datetime_calls.append(value) or value)
    monkeypatch.setattr(module, "apply_opaque_pagination_by_date", lambda **kwargs: kwargs["query"])

    result = module.find_orders({"order_schedule_from": "2026-04-29"}, _ctx(), query=query)

    assert result is query
    assert to_datetime_calls == ["2026-04-29"]
    assert query.filter_calls >= 2


def test_find_orders_accepts_order_schedule_to_alias(monkeypatch):
    query = _DummyQuery()
    state_queries = []

    def _query(model):
        state_queries.append(model)
        return _StateIdQuery([])

    to_datetime_calls = []

    monkeypatch.setattr(module.db.session, "query", _query)
    monkeypatch.setattr(module, "to_datetime", lambda value: to_datetime_calls.append(value) or value)
    monkeypatch.setattr(module, "apply_opaque_pagination_by_date", lambda **kwargs: kwargs["query"])

    result = module.find_orders({"order_schedule_to": "2026-05-02"}, _ctx(), query=query)

    assert result is query
    assert to_datetime_calls == ["2026-05-02"]
    assert query.filter_calls >= 2
