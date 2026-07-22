from types import SimpleNamespace

import pytest

from Delivery_app_BK import create_app
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.auth import (
    build_trusted_device_sessions as module,
)


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


class _Ctx:
    def __init__(self):
        self.warnings = []

    def set_warning(self, message):
        self.warnings.append(message)


class _AssignQuery:
    def __init__(self, assignments):
        self._assignments = assignments

    def filter(self, *_a, **_k):
        return self

    def options(self, *_a, **_k):
        return self

    def all(self):
        return self._assignments


def _user(uid, name):
    return SimpleNamespace(id=uid, username=name, client_id=f"user_{uid}")


def _tokens_for(user, **_kwargs):
    return {
        "access_token": f"a{user.id}",
        "refresh_token": f"r{user.id}",
        "socket_token": f"s{user.id}",
        "user": {"client_id": user.client_id, "id": user.id},
    }


def _device():
    return SimpleNamespace(id=99, client_id="tdv_1", name="Front Desk")


def _install(monkeypatch, assignments, build=_tokens_for):
    monkeypatch.setattr(module.db.session, "query", lambda _m: _AssignQuery(assignments))
    monkeypatch.setattr(module, "build_user_tokens", build)


def test_initiating_user_first_and_active_pointer(app_ctx, monkeypatch):
    initiating = _user(12, "David")
    other = _user(15, "Amanda")
    _install(monkeypatch, [SimpleNamespace(user=initiating), SimpleNamespace(user=other)])

    ctx = _Ctx()
    result = module.build_trusted_device_sessions(
        ctx, trusted_device=_device(), initiating_user=initiating,
        app_scope="driver", time_zone=None,
    )

    assert result["authentication_mode"] == "trusted_device"
    assert result["active_user_client_id"] == "user_12"
    assert result["sessions"][0]["user_client_id"] == "user_12"
    # Remaining ordered by username -> Amanda after David.
    assert [s["user_client_id"] for s in result["sessions"]] == ["user_12", "user_15"]
    assert ctx.warnings == []


def test_each_session_has_distinct_tokens(app_ctx, monkeypatch):
    initiating = _user(1, "A")
    other = _user(2, "B")
    _install(monkeypatch, [SimpleNamespace(user=initiating), SimpleNamespace(user=other)])

    result = module.build_trusted_device_sessions(
        _Ctx(), trusted_device=_device(), initiating_user=initiating,
        app_scope="driver", time_zone=None,
    )
    access = {s["access_token"] for s in result["sessions"]}
    refresh = {s["refresh_token"] for s in result["sessions"]}
    assert len(access) == 2 and len(refresh) == 2


def test_secondary_domain_error_is_excluded_as_warning(app_ctx, monkeypatch):
    initiating = _user(1, "A")
    bad = _user(2, "B")

    def build(user, **_k):
        if user.id == 2:
            raise ValidationFailed("no scope")
        return _tokens_for(user)

    _install(monkeypatch, [SimpleNamespace(user=initiating), SimpleNamespace(user=bad)], build)

    ctx = _Ctx()
    result = module.build_trusted_device_sessions(
        ctx, trusted_device=_device(), initiating_user=initiating,
        app_scope="driver", time_zone=None,
    )
    assert [s["user_client_id"] for s in result["sessions"]] == ["user_1"]
    assert ctx.warnings == [{"code": "trusted_device_users_excluded", "count": 1}]


def test_initiating_domain_error_fails_login(app_ctx, monkeypatch):
    initiating = _user(1, "A")

    def build(_user, **_k):
        raise ValidationFailed("no scope for initiator")

    _install(monkeypatch, [SimpleNamespace(user=initiating)], build)

    with pytest.raises(ValidationFailed):
        module.build_trusted_device_sessions(
            _Ctx(), trusted_device=_device(), initiating_user=initiating,
            app_scope="driver", time_zone=None,
        )


def test_cap_excludes_overflow_and_warns(app_ctx, monkeypatch):
    initiating = _user(1, "A")
    assignments = [SimpleNamespace(user=initiating)]
    for i in range(2, 40):
        assignments.append(SimpleNamespace(user=_user(i, f"U{i:02d}")))
    _install(monkeypatch, assignments)

    ctx = _Ctx()
    result = module.build_trusted_device_sessions(
        ctx, trusted_device=_device(), initiating_user=initiating,
        app_scope="driver", time_zone=None,
    )
    # Default cap is 25.
    assert len(result["sessions"]) == 25
    assert result["sessions"][0]["user_client_id"] == "user_1"
    assert ctx.warnings[0]["code"] == "trusted_device_users_excluded"
    assert ctx.warnings[0]["count"] == len(assignments) - 25
