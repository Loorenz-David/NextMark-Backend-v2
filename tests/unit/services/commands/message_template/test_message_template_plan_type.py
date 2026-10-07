from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.message_template import create_message_template as create_module
from Delivery_app_BK.services.commands.message_template import update_message_template as update_module
from Delivery_app_BK.services.context import ServiceContext


CREATE_FIELDS = {
    "client_id": "message_template_1",
    "name": "Ready for pickup",
    "event": "order_ready",
    "enable": True,
    "ask_permission": False,
    "template": [],
    "channel": "sms",
    "plan_type": "store_pickup",
    "schedule_offset_value": None,
    "schedule_offset_unit": None,
}


def _duplicate_error() -> IntegrityError:
    return IntegrityError(
        "INSERT INTO message_template",
        {},
        Exception('duplicate key value violates unique constraint "uq_message_template_team_event_channel_plan_type"'),
    )


def _stub_create(monkeypatch, *, flush):
    calls = {"rollback": 0, "commit": 0}
    monkeypatch.setattr(
        create_module,
        "create_instance",
        lambda ctx, model, fields: SimpleNamespace(
            id=1,
            event=fields["event"],
            schedule_offset_value=None,
            schedule_offset_unit=None,
        ),
    )
    monkeypatch.setattr(create_module, "validate_schedule_configuration", lambda **_kwargs: None)
    monkeypatch.setattr(create_module, "build_create_result", lambda ctx, instances: instances)
    monkeypatch.setattr(create_module.db.session, "add_all", lambda instances: None)
    monkeypatch.setattr(create_module.db.session, "flush", flush)
    monkeypatch.setattr(create_module.db.session, "rollback", lambda: calls.__setitem__("rollback", calls["rollback"] + 1))
    monkeypatch.setattr(create_module.db.session, "commit", lambda: calls.__setitem__("commit", calls["commit"] + 1))
    return calls


def test_create_requires_plan_type(monkeypatch):
    calls = _stub_create(monkeypatch, flush=lambda: None)
    fields = {key: value for key, value in CREATE_FIELDS.items() if key != "plan_type"}

    with pytest.raises(ValidationFailed, match="plan_type is required"):
        create_module.create_message_template(ServiceContext(incoming_data={"fields": fields}))

    assert calls["commit"] == 0


def test_create_reports_duplicate_plan_type_template_as_validation_error(monkeypatch):
    def _flush():
        raise _duplicate_error()

    calls = _stub_create(monkeypatch, flush=_flush)

    with pytest.raises(ValidationFailed, match="event, channel and plan type already exists"):
        create_module.create_message_template(ServiceContext(incoming_data={"fields": dict(CREATE_FIELDS)}))

    assert calls["rollback"] == 1
    assert calls["commit"] == 0


def test_create_reraises_unrelated_integrity_errors(monkeypatch):
    def _flush():
        raise IntegrityError("INSERT", {}, Exception("some other constraint"))

    _stub_create(monkeypatch, flush=_flush)

    with pytest.raises(IntegrityError):
        create_module.create_message_template(ServiceContext(incoming_data={"fields": dict(CREATE_FIELDS)}))


def test_update_reports_duplicate_plan_type_template_as_validation_error(monkeypatch):
    calls = {"rollback": 0, "commit": 0}
    monkeypatch.setattr(
        update_module,
        "update_instance",
        lambda ctx, model, fields, target_id: SimpleNamespace(
            id=target_id, event="order_ready", schedule_offset_value=None, schedule_offset_unit=None
        ),
    )
    monkeypatch.setattr(update_module, "validate_schedule_configuration", lambda **_kwargs: None)

    def _flush():
        raise _duplicate_error()

    monkeypatch.setattr(update_module.db.session, "flush", _flush)
    monkeypatch.setattr(update_module.db.session, "rollback", lambda: calls.__setitem__("rollback", calls["rollback"] + 1))
    monkeypatch.setattr(update_module.db.session, "commit", lambda: calls.__setitem__("commit", calls["commit"] + 1))

    ctx = ServiceContext(incoming_data={"target": {"target_id": 7, "fields": {"plan_type": "local_delivery"}}})

    with pytest.raises(ValidationFailed, match="event, channel and plan type already exists"):
        update_module.update_message_template(ctx)

    assert calls["rollback"] == 1
    assert calls["commit"] == 0
