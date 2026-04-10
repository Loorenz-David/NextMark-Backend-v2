from types import SimpleNamespace

from Delivery_app_BK.models import Team, User, ZoneVersion
from Delivery_app_BK.services.commands.user_registration import register_user as module


class _DummyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return None


class _ZoneVersionLookupQuery:
    def __init__(self, value=None):
        self._value = value

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._value


class _DummyCtx:
    def __init__(self):
        self.inject_team_id = True

    def set_relationship_map(self, _relationship_map):
        return self


def test_register_user_stores_normalized_default_city_key(monkeypatch):
    created = {}

    monkeypatch.setattr(
        module,
        "extract_fields",
        lambda *_args, **_kwargs: {
            "username": "anna",
            "email": "anna@example.com",
            "password": "secret",
            "phone_number": "+46000000",
            "time_zone": "Europe/Stockholm",
            "default_country_code": "SE",
            "default_city_key": "Stockholm",
        },
    )
    monkeypatch.setattr(module, "build_create_result", lambda *_args, **_kwargs: [{"ok": True}])
    monkeypatch.setattr(module, "generate_client_id", lambda _prefix: "usr_123")
    monkeypatch.setattr(module.db.session, "query", lambda _model: _DummyQuery())
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    def _fake_create_instance(_ctx, model, fields):
        created[model.__name__] = fields
        if model is User:
            return SimpleNamespace(id=1, user_role_id=1, team=None)
        if model is Team:
            return SimpleNamespace(id=2)
        raise AssertionError(f"Unexpected model: {model}")

    monkeypatch.setattr(module, "create_instance", _fake_create_instance)

    module.register_user(_DummyCtx())

    assert created["Team"]["default_city_key"] == "stockholm"


def test_register_user_accepts_country_code_alias(monkeypatch):
    created = {}

    monkeypatch.setattr(
        module,
        "extract_fields",
        lambda *_args, **_kwargs: {
            "username": "anna",
            "email": "anna@example.com",
            "password": "secret",
            "phone_number": {"prefix": "+46", "number": "701234567"},
            "time_zone": "Europe/Stockholm",
            "country_code": "SE",
            "city": "Stockholm",
        },
    )
    monkeypatch.setattr(module, "build_create_result", lambda *_args, **_kwargs: [{"ok": True}])
    monkeypatch.setattr(module, "generate_client_id", lambda _prefix: "usr_123")
    monkeypatch.setattr(module.db.session, "query", lambda _model: _DummyQuery())
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    def _fake_create_instance(_ctx, model, fields):
        created[model.__name__] = fields
        if model is User:
            return SimpleNamespace(id=1, user_role_id=1, team=None)
        if model is Team:
            return SimpleNamespace(id=2)
        raise AssertionError(f"Unexpected model: {model}")

    monkeypatch.setattr(module, "create_instance", _fake_create_instance)

    module.register_user(_DummyCtx())

    assert created["Team"]["default_country_code"] == "SE"
    assert created["Team"]["default_city_key"] == "stockholm"


def test_register_user_creates_initial_zone_version_for_default_city(monkeypatch):
    zone_versions_added = []

    monkeypatch.setattr(
        module,
        "extract_fields",
        lambda *_args, **_kwargs: {
            "username": "anna",
            "email": "anna@example.com",
            "password": "secret",
            "phone_number": "+46000000",
            "time_zone": "Europe/Stockholm",
            "default_country_code": "SE",
            "default_city_key": "Stockholm",
        },
    )
    monkeypatch.setattr(module, "build_create_result", lambda *_args, **_kwargs: [{"ok": True}])
    monkeypatch.setattr(module, "generate_client_id", lambda _prefix: "usr_123")

    def _fake_query(model):
        if model is User:
            return _DummyQuery()
        return _ZoneVersionLookupQuery(None)

    monkeypatch.setattr(module.db.session, "query", _fake_query)

    def _capture_add(instance):
        if isinstance(instance, ZoneVersion):
            zone_versions_added.append(instance)

    monkeypatch.setattr(module.db.session, "add", _capture_add)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    def _fake_create_instance(_ctx, model, fields):
        if model is User:
            return SimpleNamespace(id=1, user_role_id=1, team=None)
        if model is Team:
            return SimpleNamespace(id=2)
        raise AssertionError(f"Unexpected model: {model}")

    monkeypatch.setattr(module, "create_instance", _fake_create_instance)

    module.register_user(_DummyCtx())

    assert len(zone_versions_added) == 1
    assert zone_versions_added[0].team_id == 2
    assert zone_versions_added[0].city_key == "stockholm"
    assert zone_versions_added[0].version_number == 1
    assert zone_versions_added[0].is_active is False
