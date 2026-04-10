import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.geocoding.providers.google import client as module


def test_provider_uses_shared_secret_loader(monkeypatch):
    monkeypatch.setattr(module, "get_google_geocoding_api_key", lambda: "loaded-key")

    provider = module.GoogleGeocodingProvider()

    assert provider._api_key == "loaded-key"


def test_provider_wraps_secret_loading_failure(monkeypatch):
    def _raise():
        raise RuntimeError("missing secret")

    monkeypatch.setattr(module, "get_google_geocoding_api_key", _raise)

    with pytest.raises(ValidationFailed) as exc:
        module.GoogleGeocodingProvider()

    assert "Google geocoding credentials are not configured" in str(exc.value)
