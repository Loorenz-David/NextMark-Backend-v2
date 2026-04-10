"""
Unit tests for the geocode_address AI tool.
Stubs the orchestrator so no HTTP calls are made.
"""
import pytest

from Delivery_app_BK.ai.tools import geocode_tools as module
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.geocoding.domain.models import GeocodeResult


def _make_result(**kwargs) -> GeocodeResult:
    defaults = dict(
        street_address="Kungsgatan 5",
        postal_code="111 56",
        city="Stockholm",
        country="SE",
        lat=59.334,
        lng=18.063,
        formatted_address="Kungsgatan 5, 111 56 Stockholm, Sweden",
    )
    return GeocodeResult(**{**defaults, **kwargs})


class _DummyCtx:
    default_country_code = None


def test_tool_returns_address_object_on_success(monkeypatch):
    monkeypatch.setattr(module, "geocode_address", lambda q, country_hint=None: _make_result())

    result = module.geocode_address_tool(_DummyCtx(), q="Kungsgatan 5, Stockholm")

    assert result["found"] is True
    assert result["address_object"]["street_address"] == "Kungsgatan 5"
    assert result["address_object"]["coordinates"]["lat"] == 59.334
    assert result["address_object"]["coordinates"]["lng"] == 18.063
    assert result["address_object"]["country"] == "SE"
    assert result["can_create_without_client_address"] is False


def test_tool_returns_not_found_when_no_result(monkeypatch):
    monkeypatch.setattr(module, "geocode_address", lambda q, country_hint=None: None)

    result = module.geocode_address_tool(_DummyCtx(), q="zzz invalid address xyz")

    assert result["found"] is False
    assert result["address_object"] is None
    assert result["can_create_without_client_address"] is True
    assert "hint" in result


def test_tool_raises_on_empty_query():
    with pytest.raises(ValidationFailed):
        module.geocode_address_tool(_DummyCtx(), q="")


def test_tool_passes_country_hint(monkeypatch):
    captured = {}

    def _fake_geocode(q, country_hint=None):
        captured["country_hint"] = country_hint
        return _make_result()

    monkeypatch.setattr(module, "geocode_address", _fake_geocode)

    result = module.geocode_address_tool(_DummyCtx(), q="Kungsgatan 5", country_hint="SE")
    assert captured["country_hint"] == "SE"
    assert result["used_country_hint"] == "SE"
    assert result["country_hint_source"] == "explicit"


def test_tool_uses_team_default_country_code_when_country_hint_omitted(monkeypatch):
    captured = {}

    def _fake_geocode(q, country_hint=None):
        captured["country_hint"] = country_hint
        return _make_result()

    monkeypatch.setattr(module, "geocode_address", _fake_geocode)

    ctx = _DummyCtx()
    ctx.default_country_code = "SE"
    result = module.geocode_address_tool(ctx, q="Kungsgatan 5")

    assert captured["country_hint"] == "SE"
    assert result["used_country_hint"] == "SE"
    assert result["country_hint_source"] == "team_default"


def test_tool_address_object_keys_match_address_schema(monkeypatch):
    monkeypatch.setattr(module, "geocode_address", lambda q, country_hint=None: _make_result())

    result = module.geocode_address_tool(_DummyCtx(), q="any address")

    addr = result["address_object"]
    assert "street_address" in addr
    assert "postal_code" in addr
    assert "city" in addr
    assert "country" in addr
    assert "coordinates" in addr
    assert "lat" in addr["coordinates"]
    assert "lng" in addr["coordinates"]
