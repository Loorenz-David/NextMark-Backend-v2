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


def test_apply_order_updates_emits_client_form_submitted_for_customer_change(monkeypatch):
    order = SimpleNamespace(
        id=10,
        team_id=7,
        client_email="old@example.com",
        reference_number="reference",
        delivery_windows=[],
        delivery_plan=None,
        delivery_plan_id=None,
    )
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args: {10: order})
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

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 10, "fields": {"client_email": "new@example.com"}}],
    )

    assert [event["event_name"] for event in events] == [
        OrderEvent.EDITED.value,
        OrderEvent.CLIENT_FORM_SUBMITTED.value,
    ]


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
    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args: {11: order})
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

    _updated, events, _deltas = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [{"target_id": 11, "fields": {"reference_number": "new-reference"}}],
    )

    assert [event["event_name"] for event in events] == [OrderEvent.EDITED.value]
