from types import SimpleNamespace
import pytest

from Delivery_app_BK.services.commands.auth import refresh_socket_token as module
from Delivery_app_BK.errors import ValidationFailed


def test_refresh_socket_token_preserves_timezone_claim(monkeypatch):
    captured = {}

    def _fake_build_user_tokens(_user, **kwargs):
        captured.update(kwargs)
        return {"socket_token": "socket-token"}

    monkeypatch.setattr(module.db.session, "get", lambda *_args: SimpleNamespace(id=3))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "build_user_tokens", _fake_build_user_tokens)

    result = module.refresh_socket_token(
        SimpleNamespace(
            identity={
                "user_id": 3,
                "app_scope": "admin",
                "session_scope_id": "session-1",
                "time_zone": "Europe/Stockholm",
            }
        )
    )

    assert result == {"socket_token": "socket-token"}
    assert captured["app_scope"] == "admin"
    assert captured["session_scope_id"] == "session-1"
    assert captured["time_zone"] == "Europe/Stockholm"


def test_refresh_socket_token_falls_back_to_utc_for_legacy_claims(monkeypatch):
    with pytest.raises(ValidationFailed):
        module.refresh_socket_token(
            SimpleNamespace(
                identity={
                    "user_id": 3,
                    "team_id": 5,
                    "user_role_id": 7,
                    "base_role_id": 11,
                }
            )
        )
