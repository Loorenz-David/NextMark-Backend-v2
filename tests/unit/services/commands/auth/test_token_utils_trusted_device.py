from types import SimpleNamespace

from Delivery_app_BK.services.commands.auth import token_utils as module


_WORKSPACE = {
    "active_team_id": 21,
    "active_role_id": 4,
    "base_role_id": 2,
    "base_role": "admin",
    "current_workspace": "team",
    "has_team_workspace": True,
    "team_name": "North Team",
    "team_time_zone": "Europe/Stockholm",
    "default_country_code": "SE",
    "default_city_key": "stockholm",
}


def _user():
    return SimpleNamespace(
        id=7,
        client_id="user_abc123",
        username="anna",
        profile_picture=None,
        show_app_tutorial=False,
        email="anna@example.com",
    )


def test_user_object_includes_client_id(monkeypatch):
    monkeypatch.setattr(module, "ensure_app_workspace_state", lambda *_a, **_k: _WORKSPACE)

    _claims, user_object = module._build_auth_claims(
        _user(), app_scope="admin", session_scope_id="sess_123", time_zone=None
    )

    assert user_object["client_id"] == "user_abc123"


def test_single_user_mode_is_default(monkeypatch):
    monkeypatch.setattr(module, "ensure_app_workspace_state", lambda *_a, **_k: _WORKSPACE)

    claims, _user_object = module._build_auth_claims(
        _user(), app_scope="admin", session_scope_id="sess_123", time_zone=None
    )

    assert claims["authentication_mode"] == "single_user"
    assert "trusted_device_id" not in claims
    assert "trusted_device_client_id" not in claims


def test_trusted_device_claims_added_when_device_supplied(monkeypatch):
    monkeypatch.setattr(module, "ensure_app_workspace_state", lambda *_a, **_k: _WORKSPACE)
    device = SimpleNamespace(id=55, client_id="tdv_xyz789")

    claims, _user_object = module._build_auth_claims(
        _user(),
        app_scope="admin",
        session_scope_id="sess_123",
        time_zone=None,
        trusted_device=device,
    )

    assert claims["authentication_mode"] == "trusted_device"
    assert claims["trusted_device_id"] == 55
    assert claims["trusted_device_client_id"] == "tdv_xyz789"


def test_build_user_tokens_normal_shape_unchanged(monkeypatch):
    """Regression: normal login bundle keeps its exact top-level keys."""
    monkeypatch.setattr(module, "ensure_app_workspace_state", lambda *_a, **_k: _WORKSPACE)
    monkeypatch.setattr(module, "create_access_token", lambda **_k: "access")
    monkeypatch.setattr(module, "create_refresh_token", lambda **_k: "refresh")

    tokens = module.build_user_tokens(_user(), app_scope="admin", time_zone=None)

    assert set(tokens.keys()) == {"access_token", "refresh_token", "socket_token", "user"}
    assert tokens["user"]["client_id"] == "user_abc123"
    assert tokens["user"]["app_scope"] == "admin"
