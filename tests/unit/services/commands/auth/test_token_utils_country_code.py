from types import SimpleNamespace

from Delivery_app_BK.services.commands.auth import token_utils as module


def test_build_auth_claims_includes_default_country_code(monkeypatch):
    user = SimpleNamespace(
        id=7,
        username="anna",
        profile_picture=None,
        show_app_tutorial=False,
        email="anna@example.com",
    )

    monkeypatch.setattr(
        module,
        "ensure_app_workspace_state",
        lambda *_args, **_kwargs: {
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
        },
    )

    claims, user_object = module._build_auth_claims(
        user,
        app_scope="admin",
        session_scope_id="sess_123",
        time_zone=None,
    )

    assert claims["default_country_code"] == "SE"
    assert claims["default_city_key"] == "stockholm"
    assert claims["time_zone"] == "Europe/Stockholm"
    assert user_object["default_country_code"] == "SE"
    assert user_object["default_city_key"] == "stockholm"


def test_build_auth_claims_allows_missing_default_country_code(monkeypatch):
    user = SimpleNamespace(
        id=7,
        username="anna",
        profile_picture=None,
        show_app_tutorial=False,
        email="anna@example.com",
    )

    monkeypatch.setattr(
        module,
        "ensure_app_workspace_state",
        lambda *_args, **_kwargs: {
            "active_team_id": 21,
            "active_role_id": 4,
            "base_role_id": 2,
            "base_role": "admin",
            "current_workspace": "team",
            "has_team_workspace": True,
            "team_name": "North Team",
            "team_time_zone": "UTC",
            "default_country_code": None,
            "default_city_key": None,
        },
    )

    claims, user_object = module._build_auth_claims(
        user,
        app_scope="admin",
        session_scope_id="sess_123",
        time_zone=None,
    )

    assert claims["default_country_code"] is None
    assert claims["default_city_key"] is None
    assert user_object["default_country_code"] is None
    assert user_object["default_city_key"] is None