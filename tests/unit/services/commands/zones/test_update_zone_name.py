from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.zones.update_zone_name import update_zone_name
from Delivery_app_BK.services.context import ServiceContext


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def _ctx(incoming_data: dict) -> ServiceContext:
    return ServiceContext(incoming_data=incoming_data, identity={"active_team_id": 1})


def test_update_zone_name_active_version_succeeds(monkeypatch):
    zone = SimpleNamespace(
        id=7,
        team_id=1,
        zone_version_id=12,
        city_key="stockholm",
        name="Old Name",
        zone_type="user",
        centroid_lat=59.3,
        centroid_lng=18.0,
        geometry={"type": "Polygon", "coordinates": []},
        min_lat=59.0,
        max_lat=59.5,
        min_lng=17.8,
        max_lng=18.2,
        is_active=True,
        created_at=None,
    )

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: zone,
    )
    committed = {"value": False}
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.commit",
        lambda: committed.update(value=True),
    )

    result = update_zone_name(_ctx({"zone_id": 7, "version_id": 12, "name": "  Zone North  "}))

    assert result["id"] == 7
    assert result["name"] == "Zone North"
    assert committed["value"] is True


def test_update_zone_name_inactive_version_succeeds(monkeypatch):
    zone = SimpleNamespace(
        id=8,
        team_id=1,
        zone_version_id=12,
        city_key="stockholm",
        name="Before",
        zone_type="user",
        centroid_lat=None,
        centroid_lng=None,
        geometry=None,
        min_lat=None,
        max_lat=None,
        min_lng=None,
        max_lng=None,
        is_active=True,
        created_at=None,
    )

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: zone,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.commit",
        lambda: None,
    )

    result = update_zone_name(_ctx({"zone_id": 8, "version_id": 12, "name": "Renamed"}))

    assert result["name"] == "Renamed"


def test_update_zone_name_rejects_empty_name(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: zone,
    )

    with pytest.raises(ValidationFailed, match="name must be a non-empty string"):
        update_zone_name(_ctx({"zone_id": 7, "version_id": 12, "name": "   "}))


def test_update_zone_name_rejects_missing_name(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: zone,
    )

    with pytest.raises(ValidationFailed, match="name must be a non-empty string"):
        update_zone_name(_ctx({"zone_id": 7, "version_id": 12}))


def test_update_zone_name_not_found(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: None,
    )

    with pytest.raises(NotFound, match="Zone 7 not found"):
        update_zone_name(_ctx({"zone_id": 7, "version_id": 12, "name": "Zone"}))


def test_update_zone_name_cross_team_zone_not_found(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=999, zone_version_id=12)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_name.db.session.get",
        lambda model, pk: zone,
    )

    with pytest.raises(NotFound, match="Zone 7 not found"):
        update_zone_name(_ctx({"zone_id": 7, "version_id": 12, "name": "Zone"}))
