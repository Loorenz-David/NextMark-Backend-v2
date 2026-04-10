from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones import get_zone_template as module


class _QueryResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


def test_get_zone_template_returns_none_without_zone_id():
    ctx = ServiceContext(query_params={}, identity={"active_team_id": 1})

    result = module.get_zone_template(ctx)

    assert result is None


def test_get_zone_template_returns_none_when_version_zone_mismatch(monkeypatch, app_ctx):
    ctx = ServiceContext(
        query_params={"zone_id": 7, "version_id": 12},
        identity={"active_team_id": 1},
    )

    monkeypatch.setattr(module.Zone, "query", SimpleNamespace(filter_by=lambda **kwargs: _QueryResult(None)), raising=False)

    result = module.get_zone_template(ctx)

    assert result is None


def test_get_zone_template_returns_serialized_active_template(monkeypatch, app_ctx):
    now = datetime.now(timezone.utc)
    ctx = ServiceContext(
        query_params={"zone_id": 7, "version_id": 12},
        identity={"active_team_id": 1},
    )

    template = SimpleNamespace(
        id=99,
        team_id=1,
        zone_id=7,
        name="North Default",
        version=3,
        is_active=True,
        default_facility_id=11,
        max_orders_per_route=20,
        max_vehicles=4,
        operating_window_start="08:00",
        operating_window_end="18:00",
        eta_tolerance_seconds=300,
        vehicle_capabilities_required=["cold_chain"],
        preferred_vehicle_ids=[5, 6],
        default_route_end_strategy="round_trip",
        meta={"note": "test"},
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(
        module.Zone,
        "query",
        SimpleNamespace(filter_by=lambda **kwargs: _QueryResult(SimpleNamespace(id=7))),
        raising=False,
    )
    monkeypatch.setattr(
        module.ZoneTemplate,
        "query",
        SimpleNamespace(filter_by=lambda **kwargs: _QueryResult(template)),
        raising=False,
    )

    result = module.get_zone_template(ctx)

    assert result is not None
    assert result["id"] == 99
    assert result["zone_id"] == 7
    assert result["default_facility_id"] == 11
    assert result["max_orders_per_route"] == 20
    assert result["max_vehicles"] == 4
    assert result["operating_window_start"] == "08:00"
    assert result["operating_window_end"] == "18:00"
    assert result["eta_tolerance_seconds"] == 300
    assert result["vehicle_capabilities_required"] == ["cold_chain"]
    assert result["preferred_vehicle_ids"] == [5, 6]
    assert result["default_route_end_strategy"] == "round_trip"
    assert result["meta"] == {"note": "test"}
    assert result["is_active"] is True
