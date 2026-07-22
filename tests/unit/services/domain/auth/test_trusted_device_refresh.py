from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.auth import trusted_device as module


def test_returns_none_for_single_user_token():
    assert module.resolve_refresh_trusted_device({"authentication_mode": "single_user"}) is None
    assert module.resolve_refresh_trusted_device({}) is None


def test_raises_when_device_missing(monkeypatch):
    monkeypatch.setattr(module.db.session, "get", lambda *_a: None)
    identity = {"authentication_mode": "trusted_device", "trusted_device_id": 5, "user_id": 1}
    with pytest.raises(ValidationFailed):
        module.resolve_refresh_trusted_device(identity)


def test_raises_when_device_revoked(monkeypatch):
    device = SimpleNamespace(id=5, is_active=True, revoked_at=object())
    monkeypatch.setattr(module.db.session, "get", lambda *_a: device)
    identity = {"authentication_mode": "trusted_device", "trusted_device_id": 5, "user_id": 1}
    with pytest.raises(ValidationFailed):
        module.resolve_refresh_trusted_device(identity)


def test_raises_when_assignment_removed(monkeypatch):
    device = SimpleNamespace(id=5, is_active=True, revoked_at=None)
    monkeypatch.setattr(module.db.session, "get", lambda *_a: device)
    monkeypatch.setattr(module, "is_user_assigned_to_device", lambda uid, did: False)
    identity = {"authentication_mode": "trusted_device", "trusted_device_id": 5, "user_id": 1}
    with pytest.raises(ValidationFailed):
        module.resolve_refresh_trusted_device(identity)


def test_returns_device_when_valid(monkeypatch):
    device = SimpleNamespace(id=5, is_active=True, revoked_at=None)
    monkeypatch.setattr(module.db.session, "get", lambda *_a: device)
    monkeypatch.setattr(module, "is_user_assigned_to_device", lambda uid, did: True)
    identity = {"authentication_mode": "trusted_device", "trusted_device_id": 5, "user_id": 1}
    assert module.resolve_refresh_trusted_device(identity) is device
