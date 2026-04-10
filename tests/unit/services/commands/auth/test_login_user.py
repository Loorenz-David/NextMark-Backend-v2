from types import SimpleNamespace

from Delivery_app_BK.services.commands.auth import login_user as module


class _DummyQuery:
    def __init__(self, user):
        self._user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._user


def test_login_user_passes_timezone_to_token_builder(monkeypatch):
    login_request = SimpleNamespace(
        email="user@example.com",
        password="secret",
        app_scope="admin",
        time_zone="Europe/Stockholm",
    )
    user = SimpleNamespace(check_password=lambda value: value == "secret")
    captured = {}

    monkeypatch.setattr(module, "parse_login_request", lambda raw: login_request)
    monkeypatch.setattr(module.db.session, "query", lambda model: _DummyQuery(user))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    def _fake_build_user_tokens(user_instance, *, app_scope=None, time_zone=None):
        captured["user"] = user_instance
        captured["app_scope"] = app_scope
        captured["time_zone"] = time_zone
        return {"access_token": "token"}

    monkeypatch.setattr(module, "build_user_tokens", _fake_build_user_tokens)

    result = module.login_user_service(SimpleNamespace(incoming_data={"x": "y"}))

    assert result["access_token"] == "token"
    assert captured["user"] is user
    assert captured["app_scope"] == "admin"
    assert captured["time_zone"] == "Europe/Stockholm"
