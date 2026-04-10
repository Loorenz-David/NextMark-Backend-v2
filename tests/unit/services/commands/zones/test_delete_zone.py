from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.zones import delete_zone as module
from Delivery_app_BK.services.context import ServiceContext


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def _ctx(incoming_data: dict) -> ServiceContext:
    return ServiceContext(incoming_data=incoming_data, identity={"active_team_id": 1})


class _CountQuery:
    def __init__(self, count_value: int):
        self._count_value = count_value

    def count(self):
        return self._count_value


def test_delete_zone_success(monkeypatch, app_ctx):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)
    version = SimpleNamespace(id=12, team_id=1, is_active=False)

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: zone if model.__name__ == "Zone" else version)
    monkeypatch.setattr(module.RouteGroup, "query", SimpleNamespace(filter_by=lambda **kwargs: _CountQuery(0)), raising=False)

    deleted = {"value": False}
    committed = {"value": False}
    monkeypatch.setattr(module.db.session, "delete", lambda obj: deleted.update(value=True))
    monkeypatch.setattr(module.db.session, "commit", lambda: committed.update(value=True))

    result = module.delete_zone(_ctx({"zone_id": 7, "version_id": 12}))

    assert result == {"deleted": True, "zone_id": 7}
    assert deleted["value"] is True
    assert committed["value"] is True


def test_delete_zone_rejects_active_version(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)
    version = SimpleNamespace(id=12, team_id=1, is_active=True)

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: zone if model.__name__ == "Zone" else version)

    with pytest.raises(ValidationFailed, match="Cannot delete zones from an active version"):
        module.delete_zone(_ctx({"zone_id": 7, "version_id": 12}))


def test_delete_zone_rejects_when_route_groups_exist(monkeypatch, app_ctx):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)
    version = SimpleNamespace(id=12, team_id=1, is_active=False)

    monkeypatch.setattr(module.db.session, "get", lambda model, pk: zone if model.__name__ == "Zone" else version)
    monkeypatch.setattr(module.RouteGroup, "query", SimpleNamespace(filter_by=lambda **kwargs: _CountQuery(2)), raising=False)

    with pytest.raises(ValidationFailed, match="Route groups derived from this zone exist"):
        module.delete_zone(_ctx({"zone_id": 7, "version_id": 12}))
