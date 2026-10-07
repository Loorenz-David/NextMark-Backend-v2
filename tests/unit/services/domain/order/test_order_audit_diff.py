from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.audit import (
    ENTITY_ITEM,
    ENTITY_NOTE,
    FIELD_CREATED,
    FIELD_DELETED,
    diff_item_audit_values,
    diff_order_audit_values,
    item_created_change,
    item_deleted_change,
    snapshot_item_audit_values,
    snapshot_order_audit_values,
)


def _order(**overrides):
    values = {
        "client_email": "a@example.com",
        "client_address": {"street_address": "Main 1", "city": "Oslo"},
        "help_to_carry": False,
        "delivery_windows": [],
        "order_notes": [],
        "client_form_token_encrypted": "secret",
        "terms_accepted_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _summaries(changes):
    return [(c.field_name, c.from_value, c.to_value) for c in changes]


def test_scalar_change_is_reported_with_old_and_new_value():
    order = _order()
    before = snapshot_order_audit_values(order)
    order.client_email = "b@example.com"

    assert _summaries(diff_order_audit_values(before, snapshot_order_audit_values(order))) == [
        ("client_email", "a@example.com", "b@example.com"),
    ]


def test_no_change_and_blank_to_blank_produce_nothing():
    order = _order(client_last_name=None)
    before = snapshot_order_audit_values(order)
    order.client_last_name = ""

    assert diff_order_audit_values(before, snapshot_order_audit_values(order)) == []


def test_snapshot_is_detached_from_in_place_json_mutation():
    order = _order()
    before = snapshot_order_audit_values(order)
    order.client_address["city"] = "Bergen"

    assert _summaries(diff_order_audit_values(before, snapshot_order_audit_values(order))) == [
        (
            "client_address",
            {"street_address": "Main 1", "city": "Oslo"},
            {"street_address": "Main 1", "city": "Bergen"},
        ),
    ]


def test_secret_and_internal_fields_are_never_audited():
    order = _order()
    before = snapshot_order_audit_values(order)
    order.client_form_token_encrypted = None
    order.terms_accepted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert diff_order_audit_values(before, snapshot_order_audit_values(order)) == []
    assert "client_form_token_encrypted" not in before


def test_delivery_windows_change_is_one_entry_with_iso_values():
    start = datetime(2026, 5, 1, 9, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)
    order = _order()
    before = snapshot_order_audit_values(order)
    order.delivery_windows = [SimpleNamespace(start_at=start, end_at=end, window_type="TIME_RANGE")]

    assert _summaries(diff_order_audit_values(before, snapshot_order_audit_values(order))) == [
        (
            "delivery_windows",
            [],
            [{"start_at": start.isoformat(), "end_at": end.isoformat(), "window_type": "TIME_RANGE"}],
        ),
    ]


def test_fields_filter_limits_snapshot_to_named_fields():
    snapshot = snapshot_order_audit_values(_order(), fields=("client_email",))

    assert snapshot == {"client_email": "a@example.com"}


def test_note_edit_add_and_remove_by_type():
    order = _order(
        order_notes=[
            {"type": "GENERAL", "content": "old"},
            '{"type": "COSTUMER", "content": "ring twice"}',
        ]
    )
    before = snapshot_order_audit_values(order)
    order.order_notes = [
        {"type": "GENERAL", "content": "new"},
        {"type": "FAILURE", "content": "nobody home"},
    ]

    changes = diff_order_audit_values(before, snapshot_order_audit_values(order))

    assert all(change.entity_type == ENTITY_NOTE for change in changes)
    assert [(c.entity_id, c.from_value, c.to_value) for c in changes] == [
        ("GENERAL", "old", "new"),
        ("COSTUMER", "ring twice", None),
        ("FAILURE", None, "nobody home"),
    ]


def _item(**overrides):
    values = {
        "id": 5,
        "article_number": "SKU-1",
        "reference_number": None,
        "item_type": None,
        "quantity": 1,
        "weight": None,
        "dimension_depth": None,
        "dimension_height": None,
        "dimension_width": None,
        "properties": None,
        "item_position": None,
        "item_state_id": 1,
        "page_link": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_item_field_change_carries_item_identity():
    item = _item()
    before = snapshot_item_audit_values(item)
    item.quantity = 3

    changes = diff_item_audit_values(before, snapshot_item_audit_values(item), item)

    assert [(c.entity_type, c.entity_id, c.entity_label) for c in changes] == [
        (ENTITY_ITEM, "5", "SKU-1"),
    ]
    assert _summaries(changes) == [("quantity", 1, 3)]


def test_item_created_and_deleted_snapshots():
    item = _item(quantity=2)

    created = item_created_change(item)
    deleted = item_deleted_change(item)

    assert created.field_name == FIELD_CREATED
    assert created.from_value is None and created.to_value["quantity"] == 2
    assert deleted.field_name == FIELD_DELETED
    assert deleted.to_value is None and deleted.from_value["article_number"] == "SKU-1"
