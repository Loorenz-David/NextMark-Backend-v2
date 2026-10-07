from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.commands.order.update_order import (
    CUSTOMER_FIELDS,
    _customer_fields_changed,
    _validate_targets_update_fields,
)
from Delivery_app_BK.services.commands.order import update_order as module


def test_validate_targets_allows_mutable_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {
                "client_first_name": "Ana",
                "delivery_windows": [],
            },
        }
    ]

    _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_state_change_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {"order_state_id": 2},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_route_plan_field():
    targets = [
        {
            "target_id": 10,
            "fields": {"route_plan_id": 2},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_delivery_plan_relationship():
    targets = [
        {
            "target_id": 10,
            "fields": {"delivery_plan": 8},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_unsupported_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {"unknown_field": "value"},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


@pytest.mark.parametrize("field", sorted(CUSTOMER_FIELDS))
def test_customer_fields_changed_detects_each_customer_field(field):
    old_values = {customer_field: None for customer_field in CUSTOMER_FIELDS}
    new_values = dict(old_values)
    new_values[field] = {"updated": True}

    assert _customer_fields_changed(
        old_values=old_values,
        new_values=new_values,
    )


def test_customer_fields_changed_ignores_non_customer_fields():
    assert not _customer_fields_changed(
        old_values={"reference_number": "old"},
        new_values={"reference_number": "new"},
    )


def _capture_audit_records(monkeypatch) -> list[dict]:
    recorded: list[dict] = []
    monkeypatch.setattr(
        module,
        "record_order_audit_changes",
        lambda _ctx, **kwargs: recorded.append(kwargs),
    )
    return recorded


def test_apply_order_updates_marks_customer_section_for_customer_change(monkeypatch):
    order = SimpleNamespace(
        id=10,
        team_id=7,
        client_email="old@example.com",
        reference_number="reference",
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {10: order})
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(
        module,
        "_capture_driver_visible_values",
        lambda current: {
            "client_email": current.client_email,
            "reference_number": current.reference_number,
        },
    )
    monkeypatch.setattr(
        module,
        "inject_fields",
        lambda _ctx, existing, fields: [setattr(existing, key, value) for key, value in fields.items()],
    )

    recorded = _capture_audit_records(monkeypatch)

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 10, "fields": {"client_email": "new@example.com"}}],
    )

    # A staff edit of customer fields is not a form submission; the CUSTOMER
    # section is what carries the change to Shopify.
    assert [event["event_name"] for event in events] == [OrderEvent.EDITED.value]
    assert "customer" in events[0]["payload"]["changed_sections"]
    assert len(recorded) == 1
    assert recorded[0]["event_id"] == events[0]["event_id"]
    assert [
        (change.field_name, change.from_value, change.to_value)
        for change in recorded[0]["changes"]
    ] == [("client_email", "old@example.com", "new@example.com")]


def test_apply_order_updates_does_not_emit_client_form_submitted_for_other_change(monkeypatch):
    order = SimpleNamespace(
        id=11,
        team_id=7,
        client_email="client@example.com",
        reference_number="old-reference",
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {11: order})
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(
        module,
        "_capture_driver_visible_values",
        lambda current: {
            "client_email": current.client_email,
            "reference_number": current.reference_number,
        },
    )
    monkeypatch.setattr(
        module,
        "inject_fields",
        lambda _ctx, existing, fields: [setattr(existing, key, value) for key, value in fields.items()],
    )

    _capture_audit_records(monkeypatch)

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 11, "fields": {"reference_number": "new-reference"}}],
    )

    assert [event["event_name"] for event in events] == [OrderEvent.EDITED.value]


def test_apply_order_updates_emits_edited_event_for_fields_outside_driver_snapshot(monkeypatch):
    order = SimpleNamespace(
        id=12,
        team_id=7,
        help_to_carry=False,
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {12: order})
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(module, "_capture_driver_visible_values", lambda _current: {})
    monkeypatch.setattr(
        module,
        "inject_fields",
        lambda _ctx, existing, fields: [setattr(existing, key, value) for key, value in fields.items()],
    )
    recorded = _capture_audit_records(monkeypatch)

    _updated, events, deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 12, "fields": {"help_to_carry": True}}],
    )

    assert [event["event_name"] for event in events] == [OrderEvent.EDITED.value]
    assert events[0]["payload"] == {"changed_sections": ["details"]}
    assert recorded[0]["event_id"] == events[0]["event_id"]
    assert [
        (change.field_name, change.from_value, change.to_value)
        for change in recorded[0]["changes"]
    ] == [("help_to_carry", False, True)]
    # Section semantics that drive route freshness stay driver-visible only.
    assert deltas[0].changed_sections == ()


def test_apply_order_updates_without_changes_records_nothing(monkeypatch):
    order = SimpleNamespace(
        id=13,
        team_id=7,
        reference_number="same",
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {13: order})
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(module, "_capture_driver_visible_values", lambda _current: {})
    monkeypatch.setattr(
        module,
        "inject_fields",
        lambda _ctx, existing, fields: [setattr(existing, key, value) for key, value in fields.items()],
    )
    recorded = _capture_audit_records(monkeypatch)

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 13, "fields": {"reference_number": "same"}}],
    )

    assert events == []
    assert recorded == []


def test_linked_device_submission_is_recorded_as_the_customers(monkeypatch):
    order = SimpleNamespace(
        id=14,
        team_id=7,
        client_email="old@example.com",
        client_form_submitted_at=None,
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {14: order})
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(
        module,
        "_capture_driver_visible_values",
        lambda current: {"client_email": current.client_email},
    )
    monkeypatch.setattr(
        module,
        "inject_fields",
        lambda _ctx, existing, fields: [setattr(existing, key, value) for key, value in fields.items()],
    )
    recorded: list[dict] = []
    monkeypatch.setattr(
        module,
        "record_order_audit_changes",
        lambda _ctx, **kwargs: recorded.append(kwargs),
    )
    targets = [
        {
            "target_id": 14,
            "fields": {"client_email": "new@example.com", "submission_source": "linked_device"},
        }
    ]
    module._extract_submission_sources(targets)

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7, user_id=5),
        targets,
    )

    assert [event["event_name"] for event in events] == [
        OrderEvent.EDITED.value,
        OrderEvent.CLIENT_FORM_SUBMITTED.value,
    ]
    assert events[0]["payload"]["changed_sections"] == ["client_form_submission"]
    assert all(event["actor_id"] is None for event in events)
    assert all(event["payload"]["relayed_by_user_id"] == 5 for event in events)
    assert all(event["payload"]["submission_source"] == "linked_device" for event in events)
    assert recorded[0]["attribute_to_user"] is False
    # The changes belong to the submission, not to the realtime edit event.
    assert recorded[0]["event_id"] == events[1]["event_id"]
    assert "event_id" not in events[0]
    # ...and the edit points at them, so its notification can say what changed.
    assert events[0]["payload"]["audit_event_id"] == events[1]["event_id"]
    assert order.client_form_submitted_at is not None


def test_unknown_submission_source_is_rejected():
    with pytest.raises(ValidationFailed):
        module._extract_submission_sources(
            [{"target_id": 1, "fields": {"submission_source": "anything"}}]
        )
