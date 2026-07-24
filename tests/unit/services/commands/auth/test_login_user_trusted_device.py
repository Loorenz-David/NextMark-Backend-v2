from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.auth import login_user as module


class _DummyQuery:
    def __init__(self, user):
        self._user = user

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._user


def _setup(monkeypatch, *, assigned, device):
    login_request = SimpleNamespace(
        email="user@example.com", password="secret", app_scope="driver", time_zone=None
    )
    user = SimpleNamespace(id=12, check_password=lambda v: v == "secret")
    monkeypatch.setattr(module, "parse_login_request", lambda raw: login_request)
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(user))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "resolve_trusted_device", lambda ctx: device)
    monkeypatch.setattr(module, "is_user_assigned_to_device", lambda uid, did: assigned)
    return user


def test_trusted_login_returns_bundle_when_assigned(monkeypatch):
    device = SimpleNamespace(id=99, client_id="tdv_1", name="Desk")
    user = _setup(monkeypatch, assigned=True, device=device)

    captured = {}

    def _fake_build(ctx, *, trusted_device, initiating_user, app_scope, time_zone):
        captured["initiating_user"] = initiating_user
        captured["device"] = trusted_device
        return {"authentication_mode": "trusted_device", "sessions": []}

    monkeypatch.setattr(module, "build_trusted_device_sessions", _fake_build)

    result = module.login_user_service(SimpleNamespace(incoming_data={"x": "y"}))

    assert result["authentication_mode"] == "trusted_device"
    assert captured["initiating_user"] is user
    assert captured["device"] is device


def test_unassigned_initiator_falls_back_to_single_user_login(monkeypatch):
    device = SimpleNamespace(id=99, client_id="tdv_1", name="Desk")
    user = _setup(monkeypatch, assigned=False, device=device)
    monkeypatch.setattr(
        module, "build_trusted_device_sessions",
        lambda *a, **k: pytest.fail("must not build sessions for unassigned user"),
    )

    captured = {}

    def _fake_build_user_tokens(user_instance, *, app_scope=None, time_zone=None):
        captured["user"] = user_instance
        return {"access_token": "token"}

    monkeypatch.setattr(module, "build_user_tokens", _fake_build_user_tokens)

    result = module.login_user_service(SimpleNamespace(incoming_data={"x": "y"}))

    assert result["authentication_mode"] == "single_user"
    assert result["access_token"] == "token"
    assert captured["user"] is user


def test_invalid_device_credentials_still_reject(monkeypatch):
    """A bad/revoked device secret fails hard — no fallback to normal login."""
    _setup(monkeypatch, assigned=False, device=None)

    def _reject(_ctx):
        raise ValidationFailed("Trusted-device authentication failed.")

    monkeypatch.setattr(module, "resolve_trusted_device", _reject)
    monkeypatch.setattr(
        module, "build_user_tokens",
        lambda *a, **k: pytest.fail("must not issue tokens on bad device credentials"),
    )

    with pytest.raises(ValidationFailed):
        module.login_user_service(SimpleNamespace(incoming_data={"x": "y"}))
