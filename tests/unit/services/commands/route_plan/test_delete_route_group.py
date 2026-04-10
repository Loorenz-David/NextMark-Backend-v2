from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.route_plan import delete_route_group as module
from Delivery_app_BK.services.context import ServiceContext


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def _ctx(route_plan_id: int, route_group_id: int) -> ServiceContext:
    return ServiceContext(
        incoming_data={"route_plan_id": route_plan_id, "route_group_id": route_group_id},
        identity={"active_team_id": 1},
    )


class _CountQuery:
    def __init__(self, count_value: int):
        self._count_value = count_value

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return self._count_value


def test_delete_route_group_success(monkeypatch, app_ctx):
    route_plan = SimpleNamespace(id=42, total_orders=5)
    route_group = SimpleNamespace(
        id=9,
        team_id=1,
        route_plan_id=42,
        zone_id=7,
        is_system_default_bucket=False,
        route_plan=route_plan,
    )

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_group)
    monkeypatch.setattr(module.RouteSolution, "query", _CountQuery(0), raising=False)

    deleted = {"value": False}
    committed = {"value": False}
    recomputed = {"value": False}
    monkeypatch.setattr(module.db.session, "delete", lambda obj: deleted.update(value=True))
    monkeypatch.setattr(module.db.session, "commit", lambda: committed.update(value=True))
    monkeypatch.setattr(module, "recompute_plan_totals", lambda plan: recomputed.update(value=True))

    result = module.delete_route_group(_ctx(route_plan_id=42, route_group_id=9))

    assert result == {"deleted": True, "route_group_id": 9}
    assert deleted["value"] is True
    assert recomputed["value"] is True
    assert committed["value"] is True


def test_delete_route_group_rejects_executed_selected_route_solution(monkeypatch, app_ctx):
    route_group = SimpleNamespace(
        id=9,
        team_id=1,
        route_plan_id=42,
        zone_id=7,
        is_system_default_bucket=False,
        route_plan=SimpleNamespace(id=42),
    )

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_group)
    monkeypatch.setattr(module.RouteSolution, "query", _CountQuery(1), raising=False)

    with pytest.raises(ValidationFailed, match="in-progress or completed"):
        module.delete_route_group(_ctx(route_plan_id=42, route_group_id=9))


def test_delete_route_group_rejects_cross_plan_access(monkeypatch):
    route_group = SimpleNamespace(
        id=9,
        team_id=1,
        route_plan_id=999,
        zone_id=7,
        is_system_default_bucket=False,
    )
    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_group)

    with pytest.raises(NotFound):
        module.delete_route_group(_ctx(route_plan_id=42, route_group_id=9))


def test_delete_route_group_rejects_no_zone_group(monkeypatch, app_ctx):
    route_group = SimpleNamespace(
        id=9,
        team_id=1,
        route_plan_id=42,
        zone_id=None,
        is_system_default_bucket=True,
        route_plan=SimpleNamespace(id=42),
    )
    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_group)

    with pytest.raises(ValidationFailed, match="cannot be deleted"):
        module.delete_route_group(_ctx(route_plan_id=42, route_group_id=9))


def test_delete_route_group_allows_manual_no_zone_group(monkeypatch, app_ctx):
    route_plan = SimpleNamespace(id=42, total_orders=5)
    route_group = SimpleNamespace(
        id=19,
        team_id=1,
        route_plan_id=42,
        zone_id=None,
        is_system_default_bucket=False,
        route_plan=route_plan,
    )

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_group)
    monkeypatch.setattr(module.RouteSolution, "query", _CountQuery(0), raising=False)

    deleted = {"value": False}
    monkeypatch.setattr(module.db.session, "delete", lambda obj: deleted.update(value=True))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "recompute_plan_totals", lambda plan: None)

    result = module.delete_route_group(_ctx(route_plan_id=42, route_group_id=19))

    assert result == {"deleted": True, "route_group_id": 19}
    assert deleted["value"] is True
