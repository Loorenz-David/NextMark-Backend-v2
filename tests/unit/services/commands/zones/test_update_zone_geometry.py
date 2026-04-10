from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.zones.update_zone_geometry import update_zone_geometry
from Delivery_app_BK.services.context import ServiceContext


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def _ctx(incoming_data: dict) -> ServiceContext:
    return ServiceContext(incoming_data=incoming_data, identity={"active_team_id": 1})


def test_update_zone_geometry_inactive_version_succeeds(app_ctx, monkeypatch):
    zone = SimpleNamespace(
        id=7,
        team_id=1,
        zone_version_id=12,
        city_key="stockholm",
        name="Zone",
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
    version = SimpleNamespace(id=12, team_id=1, is_active=False)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.get",
        lambda model, pk: zone if model.__name__ == "Zone" else version,
    )
    state = {"flush_called": False, "refresh_called": False, "committed": False}
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.flush",
        lambda: state.update(flush_called=True),
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.refresh_zone_geometry_derivatives",
        lambda zone_id: state.update(refresh_called=(zone_id == 7)),
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.commit",
        lambda: state.update(committed=True),
    )

    result = update_zone_geometry(
        _ctx(
            {
                "zone_id": 7,
                "version_id": 12,
                "geometry": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [1, 2]]]},
            }
        )
    )

    assert result["id"] == 7
    assert state["flush_called"] is True
    assert state["refresh_called"] is True
    assert state["committed"] is True


def test_update_zone_geometry_rejects_active_version(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)
    version = SimpleNamespace(id=12, team_id=1, is_active=True)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.get",
        lambda model, pk: zone if model.__name__ == "Zone" else version,
    )

    with pytest.raises(
        ValidationFailed,
        match="Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries.",
    ):
        update_zone_geometry(_ctx({"zone_id": 7, "version_id": 12, "geometry": {}}))


def test_update_zone_geometry_requires_spatial_fields(monkeypatch):
    zone = SimpleNamespace(id=7, team_id=1, zone_version_id=12)
    version = SimpleNamespace(id=12, team_id=1, is_active=False)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.get",
        lambda model, pk: zone if model.__name__ == "Zone" else version,
    )

    with pytest.raises(ValidationFailed, match="No geometry fields provided."):
        update_zone_geometry(_ctx({"zone_id": 7, "version_id": 12, "name": "Nope"}))


def test_update_zone_geometry_refresh_called_when_geometry_present(monkeypatch):
    zone = SimpleNamespace(
        id=9,
        team_id=1,
        zone_version_id=12,
        city_key="stockholm",
        name="Zone",
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
    version = SimpleNamespace(id=12, team_id=1, is_active=False)

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.get",
        lambda model, pk: zone if model.__name__ == "Zone" else version,
    )
    state = {"refresh_called": False}
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.flush",
        lambda: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.refresh_zone_geometry_derivatives",
        lambda zone_id: state.update(refresh_called=(zone_id == 9)),
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.commit",
        lambda: None,
    )

    update_zone_geometry(_ctx({"zone_id": 9, "version_id": 12, "geometry": {"type": "Polygon", "coordinates": []}}))

    assert state["refresh_called"] is True


def test_update_zone_geometry_zone_not_found(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.update_zone_geometry.db.session.get",
        lambda model, pk: None,
    )

    with pytest.raises(NotFound, match="Zone 7 not found"):
        update_zone_geometry(_ctx({"zone_id": 7, "version_id": 12, "geometry": {}}))
