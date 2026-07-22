from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.commands.auth import trusted_device_common as common
from Delivery_app_BK.services.commands.auth import assign_trusted_device_user as assign_mod
from Delivery_app_BK.services.commands.auth import get_trusted_device_users as list_mod
from Delivery_app_BK.services.commands.auth import resync_trusted_device_sessions as resync_mod


class _Query:
    def __init__(self, result):
        self._result = result

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._result


def _ctx(**kw):
    base = dict(team_id=10, user_id=1, incoming_data={}, warnings=[])
    base.update(kw)
    ns = SimpleNamespace(**base)
    ns.set_warning = ns.warnings.append
    return ns


# --- cross-team isolation ------------------------------------------------

def test_load_team_device_missing_or_other_team_raises(monkeypatch):
    # Query scoped by team_id returns nothing for another team's device.
    monkeypatch.setattr(common.db.session, "query", lambda _m: _Query(None))
    with pytest.raises(NotFound):
        common.load_team_device(_ctx(), "tdv_other_team")


def test_load_team_user_missing_raises(monkeypatch):
    monkeypatch.setattr(common.db.session, "query", lambda _m: _Query(None))
    with pytest.raises(NotFound):
        common.load_team_user_by_client_id(_ctx(), "user_x")


# --- duplicate assignment prevention -------------------------------------

def test_assign_rejects_already_active(monkeypatch):
    device = SimpleNamespace(id=99)
    user = SimpleNamespace(id=5, client_id="user_5", username="u", profile_picture=None)
    monkeypatch.setattr(assign_mod, "parse_assign_trusted_device_user",
                        lambda raw: SimpleNamespace(user_client_id="user_5"))
    monkeypatch.setattr(assign_mod, "load_team_device", lambda ctx, cid: device)
    monkeypatch.setattr(assign_mod, "load_team_user_by_client_id", lambda ctx, cid: user)
    existing = SimpleNamespace(is_active=True)
    monkeypatch.setattr(assign_mod.db.session, "query", lambda _m: _Query(existing))

    with pytest.raises(ValidationFailed):
        assign_mod.assign_trusted_device_user(_ctx(), "tdv_1")


# --- device-credential endpoints -----------------------------------------

def test_list_users_requires_valid_device(monkeypatch):
    monkeypatch.setattr(list_mod, "resolve_trusted_device", lambda ctx: None)
    with pytest.raises(ValidationFailed):
        list_mod.get_trusted_device_users(_ctx())


def test_resync_rejects_unassigned_user(monkeypatch):
    device = SimpleNamespace(id=99)
    monkeypatch.setattr(resync_mod, "resolve_trusted_device", lambda ctx: device)
    monkeypatch.setattr(resync_mod.db.session, "get", lambda *_a: SimpleNamespace(id=1))
    monkeypatch.setattr(resync_mod, "is_user_assigned_to_device", lambda uid, did: False)
    ctx = _ctx(app_scope="driver", time_zone=None)
    with pytest.raises(ValidationFailed):
        resync_mod.resync_trusted_device_sessions(ctx)
