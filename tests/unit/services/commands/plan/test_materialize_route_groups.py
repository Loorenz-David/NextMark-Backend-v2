from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.route_plan import materialize_route_groups as module
from Delivery_app_BK.services.context import ServiceContext


class _QueryResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _ZoneListQuery:
    def __init__(self, zones):
        self._zones = zones

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._zones)


class _AggregateQuery:
    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return []


@contextmanager
def _noop_nested_txn():
    yield


def _make_ctx(zone_ids=None):
    return ServiceContext(
        incoming_data={"route_plan_id": 42, "zone_ids": zone_ids or [7]},
        identity={"active_team_id": 1},
    )


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def test_normalize_zone_ids_dedupes_and_validates_positive_ints():
    assert module._normalize_zone_ids([7, 7, 9]) == [7, 9]

    with pytest.raises(ValidationFailed):
        module._normalize_zone_ids([])

    with pytest.raises(ValidationFailed):
        module._normalize_zone_ids([0])


def test_materialize_route_groups_raises_not_found_for_missing_plan(monkeypatch):
    monkeypatch.setattr(module.db.session, "get", lambda model, id_value: None)

    with pytest.raises(NotFound):
        module.materialize_route_groups(_make_ctx())


def test_materialize_route_groups_returns_existing_route_group(monkeypatch, app_ctx):
    existing = SimpleNamespace(id=101, zone_id=7, total_orders=None)
    route_plan = SimpleNamespace(id=42, team_id=1)
    zone = SimpleNamespace(id=7, name="Zone North", geometry={"type": "Polygon", "coordinates": []})
    observed_plan_ids: list[int] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, id_value: route_plan)
    monkeypatch.setattr(module.Zone, "query", _ZoneListQuery([zone]), raising=False)
    monkeypatch.setattr(module.RouteGroup, "query", SimpleNamespace(filter_by=lambda **kwargs: _QueryResult(existing)), raising=False)
    monkeypatch.setattr(module.db.session, "query", lambda *args, **kwargs: _AggregateQuery())
    monkeypatch.setattr(module.db.session, "begin_nested", _noop_nested_txn)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(
        module,
        "recompute_route_group_totals",
        lambda plan: observed_plan_ids.append(plan.id),
    )
    monkeypatch.setattr(module, "serialize_route_group", lambda route_group, ctx: {"id": route_group.id})

    result = module.materialize_route_groups(_make_ctx())

    assert result == [{"id": 101}]
    assert observed_plan_ids == [42]
