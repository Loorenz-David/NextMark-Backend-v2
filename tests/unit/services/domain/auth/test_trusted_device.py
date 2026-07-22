from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.auth import trusted_device as module


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


class _DummyQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._result


def _ctx(client_id=None, secret=None):
    return SimpleNamespace(
        trusted_device_client_id=client_id,
        trusted_device_secret=secret,
    )


def test_secret_hash_roundtrip(app_ctx):
    raw = module.generate_device_secret()
    stored = module.hash_device_secret(raw)
    assert stored != raw
    assert module.verify_device_secret(raw, stored) is True


def test_verify_rejects_wrong_secret(app_ctx):
    stored = module.hash_device_secret("correct-secret")
    assert module.verify_device_secret("wrong-secret", stored) is False
    assert module.verify_device_secret("", stored) is False
    assert module.verify_device_secret("correct-secret", "") is False


def test_resolve_returns_none_without_credentials():
    assert module.resolve_trusted_device(_ctx()) is None


def test_resolve_raises_on_partial_credentials():
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id="tdv_x", secret=None))
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id=None, secret="s"))


def test_resolve_raises_when_device_missing(monkeypatch):
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(None))
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id="tdv_x", secret="s"))


def test_resolve_raises_when_inactive(monkeypatch):
    device = SimpleNamespace(is_active=False, revoked_at=None, device_secret_hash="h")
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(device))
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id="tdv_x", secret="s"))


def test_resolve_raises_when_revoked(monkeypatch):
    device = SimpleNamespace(is_active=True, revoked_at=object(), device_secret_hash="h")
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(device))
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id="tdv_x", secret="s"))


def test_resolve_raises_on_bad_secret(monkeypatch):
    device = SimpleNamespace(is_active=True, revoked_at=None, device_secret_hash="h", last_used_at=None)
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(device))
    monkeypatch.setattr(module, "verify_device_secret", lambda *_a: False)
    with pytest.raises(ValidationFailed):
        module.resolve_trusted_device(_ctx(client_id="tdv_x", secret="bad"))


def test_resolve_succeeds_and_stamps_last_used(monkeypatch):
    device = SimpleNamespace(is_active=True, revoked_at=None, device_secret_hash="h", last_used_at=None)
    monkeypatch.setattr(module.db.session, "query", lambda _m: _DummyQuery(device))
    monkeypatch.setattr(module, "verify_device_secret", lambda *_a: True)
    result = module.resolve_trusted_device(_ctx(client_id="tdv_x", secret="good"))
    assert result is device
    assert device.last_used_at is not None
