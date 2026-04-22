import importlib

import pytest

from Delivery_app_BK.errors import ValidationFailed


module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_logistic.auth.verify_api_key"
)


def test_verify_api_key_accepts_matching_header(monkeypatch):
    monkeypatch.setattr(module, "LOGISTIC_API_KEY", "secret")

    module.verify_api_key({"x-api-key": "secret"})


def test_verify_api_key_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(module, "LOGISTIC_API_KEY", "secret")

    with pytest.raises(ValidationFailed):
        module.verify_api_key({})


def test_verify_api_key_rejects_mismatched_header(monkeypatch):
    monkeypatch.setattr(module, "LOGISTIC_API_KEY", "secret")

    with pytest.raises(ValidationFailed):
        module.verify_api_key({"X-Api-Key": "wrong"})
