from types import SimpleNamespace

import pytest

from Delivery_app_BK.services.commands.order.client_form import submit_client_form as module
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.commands.order.update_extensions.types import (
    OrderUpdateChangeFlags,
    OrderUpdateExtensionResult,
)


@pytest.fixture(autouse=True)
def audit_records(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(
        module,
        "record_order_audit_changes",
        lambda _ctx, **kwargs: recorded.append(kwargs),
    )
    return recorded


@pytest.fixture(autouse=True)
def _no_terms_configured(monkeypatch):
    """Default for these tests: the team collects no terms acceptance.

    Terms acceptance is covered separately in test_submit_client_form_terms.py.
    """
    monkeypatch.setattr(module, "resolve_terms_acceptance", lambda team_id, payload: None)


def test_submit_client_form_persists_allowed_fields_and_emits_submission_events(monkeypatch, audit_records):
    order = SimpleNamespace(
        id=42,
        team_id=7,
        client_email="old@example.com",
        client_primary_phone={"prefix": "+1", "number": "5550000"},
        client_form_token_encrypted="encrypted-token",
        client_form_submitted_at=None,
    )
    emitted_events: list[dict] = []

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: emitted_events.extend(events))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    result = module.submit_client_form(
        "valid-token",
        {
            "client_email": "new@example.com",
            "client_primary_phone": {"prefix": "+46", "number": "2020203"},
            "unexpected_field": "ignore-me",
        },
    )

    assert result == {"success": True}
    assert order.client_email == "new@example.com"
    assert order.client_primary_phone == {"prefix": "+46", "number": "2020203"}
    assert not hasattr(order, "unexpected_field")
    assert order.client_form_submitted_at is not None
    assert order.client_form_token_encrypted is None

    assert len(emitted_events) == 2
    assert emitted_events[0]["order_id"] == 42
    assert emitted_events[0]["team_id"] == 7
    assert emitted_events[0]["event_name"] == OrderEvent.EDITED.value
    assert emitted_events[0]["payload"]["changed_sections"] == ["client_form_submission"]
    # The changes belong to the submission, not to the realtime edit event.
    assert "event_id" not in emitted_events[0]
    assert audit_records[0]["event_id"] == emitted_events[1]["event_id"]
    assert sorted(
        (change.field_name, change.from_value, change.to_value)
        for change in audit_records[0]["changes"]
    ) == [
        ("client_email", "old@example.com", "new@example.com"),
        (
            "client_primary_phone",
            {"number": "5550000", "prefix": "+1"},
            {"number": "2020203", "prefix": "+46"},
        ),
    ]
    assert {key: value for key, value in emitted_events[1].items() if key != "event_id"} == {
        "order_id": 42,
        "team_id": 7,
        "event_name": OrderEvent.CLIENT_FORM_SUBMITTED.value,
        "payload": {},
    }


def test_submit_client_form_ignores_non_allowed_payload_keys(monkeypatch):
    order = SimpleNamespace(
        id=9,
        team_id=3,
        client_first_name="Old",
        client_form_token_encrypted="encrypted-token",
        client_form_submitted_at=None,
    )
    emitted_events: list[dict] = []

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: emitted_events.extend(events))
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    module.submit_client_form(
        "valid-token",
        {
            "client_first_name": "New",
            "hacker_field": "should-not-persist",
        },
    )

    assert order.client_first_name == "New"
    assert not hasattr(order, "hacker_field")
    assert len(emitted_events) == 2
    assert emitted_events[1]["event_name"] == OrderEvent.CLIENT_FORM_SUBMITTED.value


def test_submit_triggers_route_extension_when_address_in_payload(monkeypatch):
    order = SimpleNamespace(
        id=5,
        team_id=2,
        client_address=None,
        delivery_plan=None,
        client_form_token_encrypted="tok",
        client_form_submitted_at=None,
    )
    captured_deltas: list = []

    def _fake_build_ctx(ctx, deltas):
        return SimpleNamespace(by_plan_type={})

    def _fake_apply(ctx, deltas, ext_ctx):
        captured_deltas.extend(deltas)
        return OrderUpdateExtensionResult()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "build_order_update_extension_context", _fake_build_ctx)
    monkeypatch.setattr(module, "apply_order_update_extensions", _fake_apply)

    module.submit_client_form(
        "valid-token",
        {"client_address": {"street": "New St 1"}},
    )

    assert len(captured_deltas) == 1
    assert captured_deltas[0].flags == OrderUpdateChangeFlags(address_changed=True)
    assert captured_deltas[0].order_instance is order


def test_submit_skips_route_extension_when_no_address_in_payload(monkeypatch):
    order = SimpleNamespace(
        id=6,
        team_id=2,
        client_email="old@example.com",
        delivery_plan=None,
        client_form_token_encrypted="tok",
        client_form_submitted_at=None,
    )
    extension_called = []

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(
        module,
        "apply_order_update_extensions",
        lambda *a, **kw: extension_called.append(True) or OrderUpdateExtensionResult(),
    )

    module.submit_client_form(
        "valid-token",
        {"client_email": "new@example.com"},
    )

    assert extension_called == [], "extension must not run when address is not in payload"


def test_submit_replaces_existing_costumer_note(monkeypatch):
    order = SimpleNamespace(
        id=7,
        team_id=2,
        order_notes=[
            {"type": "GENERAL", "content": "existing"},
            {"type": "COSTUMER", "content": "old client note"},
        ],
        client_form_token_encrypted="tok",
        client_form_submitted_at=None,
    )

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    module.submit_client_form(
        "valid-token",
        {
            "order_notes": {"type": "COSTUMER", "content": "new note"},
        },
    )

    assert order.order_notes == [
        {"type": "GENERAL", "content": "existing"},
        {"type": "COSTUMER", "content": "new note"},
    ]


def test_submit_initializes_order_notes_list_when_missing(monkeypatch):
    order = SimpleNamespace(
        id=8,
        team_id=2,
        order_notes=None,
        client_form_token_encrypted="tok",
        client_form_submitted_at=None,
    )

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    module.submit_client_form(
        "valid-token",
        {
            "order_notes": {"type": "COSTUMER", "content": "first note"},
        },
    )

    assert order.order_notes == [{"type": "COSTUMER", "content": "first note"}]
