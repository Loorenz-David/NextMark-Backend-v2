from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.zones.ensure_first_zone_version import (
    ensure_first_zone_version,
)
from Delivery_app_BK.services.context import ServiceContext


class _QueryResult:
    def __init__(self, value):
        self._value = value

    def filter_by(self, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._value


@pytest.fixture
def ctx() -> ServiceContext:
    return ServiceContext(
        incoming_data={"city_key": "Stockholm"},
        identity={"active_team_id": 1},
    )


def test_ensure_first_zone_version_returns_latest_if_exists(monkeypatch, ctx):
    existing = SimpleNamespace(
        id=12,
        team_id=1,
        city_key="stockholm",
        version_number=3,
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.query",
        lambda *_args, **_kwargs: _QueryResult(existing),
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.get",
        lambda *_args, **_kwargs: SimpleNamespace(id=1),
    )

    committed = {"value": False}
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.commit",
        lambda: committed.update(value=True),
    )

    result = ensure_first_zone_version(ctx)

    assert result["id"] == 12
    assert result["version_number"] == 3
    assert committed["value"] is False


def test_ensure_first_zone_version_creates_v1_when_missing(monkeypatch, ctx):
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.query",
        lambda *_args, **_kwargs: _QueryResult(None),
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.get",
        lambda *_args, **_kwargs: SimpleNamespace(id=1),
    )

    added = {"version": None}

    def _capture_add(model):
        added["version"] = model

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.add",
        _capture_add,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.commit",
        lambda: None,
    )

    result = ensure_first_zone_version(ctx)

    assert added["version"] is not None
    assert added["version"].team_id == 1
    assert added["version"].city_key == "stockholm"
    assert added["version"].version_number == 1
    assert added["version"].is_active is False
    assert result["version_number"] == 1


def test_ensure_first_zone_version_requires_city_key():
    with pytest.raises(ValidationFailed, match="city_key is required"):
        ensure_first_zone_version(
            ServiceContext(incoming_data={}, identity={"active_team_id": 1})
        )


def test_ensure_first_zone_version_raises_when_team_missing(monkeypatch, ctx):
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.zones.ensure_first_zone_version.db.session.get",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(NotFound, match="Team 1 not found"):
        ensure_first_zone_version(ctx)
