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


def _ctx(**overrides):
    base = {"inject_team_id": False, "query_params": {}, "team_id": 7}
    base.update(overrides)
    return SimpleNamespace(**base)


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


def _patched(monkeypatch):
    monkeypatch.setattr(module.db.session, "query", lambda _model: _StateIdQuery([]))
    monkeypatch.setattr(module, "apply_opaque_pagination_by_date", lambda **kwargs: kwargs["query"])


class _RecordingQuery(_DummyQuery):
    def __init__(self):
        super().__init__()
        self.filter_args = []

    def filter(self, *args, **_kwargs):
        self.filter_args.append(args)
        return super().filter(*args, **_kwargs)


def _filter_strings(query):
    return [str(arg) for call in query.filter_args for arg in call]


def test_find_orders_false_unschedule_flag_adds_no_schedule_filter(monkeypatch):
    _patched(monkeypatch)
    flagged = _RecordingQuery()
    module.find_orders({"unschedule_order": "false"}, _ctx(), query=flagged)

    baseline = _RecordingQuery()
    module.find_orders({}, _ctx(), query=baseline)

    assert flagged.filter_calls == baseline.filter_calls


def test_find_orders_true_unschedule_flag_filters_unscheduled(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"unschedule_order": "true"}, _ctx(), query=query)

    assert any("route_plan_id IS NULL" in text for text in _filter_strings(query))


def test_find_orders_scheduled_wins_over_unscheduled(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"schedule_order": True, "unschedule_order": True}, _ctx(), query=query)

    texts = _filter_strings(query)
    assert any("route_plan_id IS NOT NULL" in text for text in texts)
    assert not any("route_plan_id IS NULL" in text for text in texts)


def test_find_orders_plan_type_list_filters_objective(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"plan_type": ["store_pickup", "local_delivery"]}, _ctx(), query=query)

    assert any("order_plan_objective IN" in text for text in _filter_strings(query))


def test_find_orders_without_plan_type_adds_no_objective_filter(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({}, _ctx(), query=query)

    assert not any("order_plan_objective" in text for text in _filter_strings(query))


def test_find_orders_ignores_caller_supplied_team_id(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"team_id": 999}, _ctx(inject_team_id=True, team_id=7), query=query)

    team_filters = [
        arg
        for call in query.filter_args
        for arg in call
        if getattr(getattr(arg, "left", None), "key", None) == "team_id"
    ]
    assert team_filters, "team filter should be applied"
    assert all(arg.right.value == 7 for arg in team_filters)


def test_find_orders_plan_type_none_sentinel_matches_null_objective(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"plan_type": ["none"]}, _ctx(), query=query)

    texts = _filter_strings(query)
    assert any("order_plan_objective IS NULL" in text for text in texts)
    assert not any("order_plan_objective IN" in text for text in texts)


def test_find_orders_plan_type_none_combines_with_concrete_types(monkeypatch):
    _patched(monkeypatch)
    query = _RecordingQuery()
    module.find_orders({"plan_type": ["store_pickup", "none"]}, _ctx(), query=query)

    combined = [
        text
        for text in _filter_strings(query)
        if "order_plan_objective IN" in text and "order_plan_objective IS NULL" in text
    ]
    assert combined, "null objective and concrete types should be OR-ed in one filter"
    assert " OR " in combined[0]
