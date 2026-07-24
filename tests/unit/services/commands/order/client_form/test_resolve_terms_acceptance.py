from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.client_form import (
    _resolve_terms_acceptance as module,
)


def _settings(*, terms_enabled=True, require_acceptance=True):
    return SimpleNamespace(
        terms_enabled=terms_enabled,
        require_acceptance=require_acceptance,
    )


def _stub(monkeypatch, settings, active_version):
    monkeypatch.setattr(module, "find_settings_for_team", lambda team_id: settings)
    monkeypatch.setattr(module, "get_active_terms_version", lambda team_id: active_version)


def test_returns_none_when_team_has_no_settings(monkeypatch):
    _stub(monkeypatch, None, None)

    assert module.resolve_terms_acceptance(7, {}) is None


def test_returns_none_when_terms_disabled(monkeypatch):
    _stub(monkeypatch, _settings(terms_enabled=False), SimpleNamespace(id=3))

    assert module.resolve_terms_acceptance(7, {"accepted_terms_version_id": 3}) is None


def test_returns_active_version_when_accepted(monkeypatch):
    active = SimpleNamespace(id=12, version_number=4)
    _stub(monkeypatch, _settings(), active)

    result = module.resolve_terms_acceptance(7, {"accepted_terms_version_id": 12})

    assert result is active


def test_optional_acceptance_may_be_omitted(monkeypatch):
    _stub(monkeypatch, _settings(require_acceptance=False), SimpleNamespace(id=12))

    assert module.resolve_terms_acceptance(7, {}) is None


def test_rejects_missing_acceptance_when_required(monkeypatch):
    _stub(monkeypatch, _settings(), SimpleNamespace(id=12))

    with pytest.raises(ValidationFailed, match="must accept the terms"):
        module.resolve_terms_acceptance(7, {})


def test_rejects_stale_or_foreign_version_id(monkeypatch):
    """A version id from another team, or a superseded one, must never be stored."""
    _stub(monkeypatch, _settings(), SimpleNamespace(id=12))

    with pytest.raises(ValidationFailed, match="no longer current"):
        module.resolve_terms_acceptance(7, {"accepted_terms_version_id": 11})


def test_rejects_non_integer_version_id(monkeypatch):
    _stub(monkeypatch, _settings(), SimpleNamespace(id=12))

    with pytest.raises(ValidationFailed, match="must be an integer"):
        module.resolve_terms_acceptance(7, {"accepted_terms_version_id": "12"})


def test_rejects_required_acceptance_with_nothing_published(monkeypatch):
    _stub(monkeypatch, _settings(), None)

    with pytest.raises(ValidationFailed, match="no terms version has been published"):
        module.resolve_terms_acceptance(7, {})
