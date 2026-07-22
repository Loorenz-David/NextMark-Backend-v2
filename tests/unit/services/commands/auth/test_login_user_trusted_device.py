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


def test_trusted_login_rejects_unassigned_initiator(monkeypatch):
    device = SimpleNamespace(id=99, client_id="tdv_1", name="Desk")
    _setup(monkeypatch, assigned=False, device=device)
    monkeypatch.setattr(
        module, "build_trusted_device_sessions",
        lambda *a, **k: pytest.fail("must not build sessions for unassigned user"),
    )

    with pytest.raises(ValidationFailed):
        module.login_user_service(SimpleNamespace(incoming_data={"x": "y"}))
