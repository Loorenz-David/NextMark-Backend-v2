import importlib
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed

# The package re-exports each command under its module's name, so the modules
# are imported explicitly to patch their globals.
activate_module = importlib.import_module(
    "Delivery_app_BK.services.commands.client_form_config.activate_client_form_redirect"
)
update_module = importlib.import_module(
    "Delivery_app_BK.services.commands.client_form_config.update_client_form_redirect"
)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self._result


@pytest.fixture
def session_log(monkeypatch):
    log: list[str] = []
    monkeypatch.setattr(activate_module, "require_team_id", lambda ctx: 7)
    monkeypatch.setattr(activate_module.db.session, "flush", lambda: log.append("flush"))
    monkeypatch.setattr(activate_module.db.session, "commit", lambda: log.append("commit"))
    return log


def _ctx(incoming):
    return SimpleNamespace(incoming_data=incoming)


def test_activate_switches_active_row_and_flushes_deactivation_first(monkeypatch, session_log):
    current = SimpleNamespace(id=1, is_active=True)
    target = SimpleNamespace(id=2, is_active=False)
    monkeypatch.setattr(activate_module, "get_instance", lambda ctx, model, value: target)
    monkeypatch.setattr(
        activate_module.db.session, "query", lambda model: _FakeQuery(current)
    )

    def _flush():
        # The partial unique index must never see two active rows.
        assert target.is_active is False
        session_log.append("flush")

    monkeypatch.setattr(activate_module.db.session, "flush", _flush)

    result = activate_module.activate_client_form_redirect(_ctx({"target_id": 2}))

    assert result == {"active_id": 2}
    assert current.is_active is False
    assert target.is_active is True
    assert session_log == ["flush", "commit"]


def test_activate_null_turns_redirect_off(monkeypatch, session_log):
    current = SimpleNamespace(id=1, is_active=True)
    monkeypatch.setattr(
        activate_module, "get_instance", lambda *a, **k: pytest.fail("no lookup expected")
    )
    monkeypatch.setattr(
        activate_module.db.session, "query", lambda model: _FakeQuery(current)
    )

    result = activate_module.activate_client_form_redirect(_ctx({"target_id": None}))

    assert result == {"active_id": None}
    assert current.is_active is False


def test_activate_already_active_target_is_a_no_op(monkeypatch, session_log):
    target = SimpleNamespace(id=2, is_active=True)
    monkeypatch.setattr(activate_module, "get_instance", lambda ctx, model, value: target)
    monkeypatch.setattr(
        activate_module.db.session, "query", lambda model: _FakeQuery(target)
    )

    activate_module.activate_client_form_redirect(_ctx({"target_id": 2}))

    assert target.is_active is True
    assert session_log == ["commit"]


def test_activate_foreign_target_fails_before_deactivating(monkeypatch, session_log):
    current = SimpleNamespace(id=1, is_active=True)

    def _foreign(ctx, model, value):
        raise ValidationFailed("Instance does not belong to this team.")

    monkeypatch.setattr(activate_module, "get_instance", _foreign)
    monkeypatch.setattr(
        activate_module.db.session, "query", lambda model: _FakeQuery(current)
    )

    with pytest.raises(ValidationFailed):
        activate_module.activate_client_form_redirect(_ctx({"target_id": 99}))

    assert current.is_active is True
    assert session_log == []


@pytest.mark.parametrize("incoming", [{}, {"target_id": "2"}, {"target_id": True}, {"target_id": 1.5}])
def test_activate_rejects_bad_payload(incoming, session_log):
    with pytest.raises(ValidationFailed):
        activate_module.activate_client_form_redirect(_ctx(incoming))


def test_update_never_writes_is_active(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(
        update_module,
        "update_instance",
        lambda ctx, model, fields, target_id: captured.append(fields) or SimpleNamespace(id=target_id),
    )
    monkeypatch.setattr(update_module.db.session, "commit", lambda: None)
    ctx = SimpleNamespace(
        incoming_data={
            "target": {
                "target_id": 3,
                "fields": {"label": "Site", "url": "https://acme.se", "is_active": True, "team_id": 99},
            }
        },
        set_relationship_map=lambda mapping: None,
    )

    assert update_module.update_client_form_redirect(ctx) == [3]
    assert captured == [{"label": "Site", "url": "https://acme.se"}]
