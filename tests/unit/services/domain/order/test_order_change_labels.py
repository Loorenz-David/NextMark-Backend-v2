from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.audit import (
    ENTITY_ITEM,
    ENTITY_NOTE,
    FIELD_CREATED,
    FIELD_DELETED,
    OrderFieldChange,
    label_order_changes,
    summarize_change_labels,
)


def test_labels_order_fields_in_recording_order_without_duplicates():
    changes = [
        OrderFieldChange("client_email", "a@x.com", "b@x.com"),
        OrderFieldChange("client_address", {"city": "A"}, {"city": "B"}),
        OrderFieldChange("client_email", "b@x.com", "c@x.com"),
    ]

    assert label_order_changes(changes) == ["Email", "Address"]


def test_labels_items_and_notes():
    changes = [
        OrderFieldChange(FIELD_CREATED, None, {"quantity": 1}, ENTITY_ITEM, "3", "ABC-1"),
        OrderFieldChange(FIELD_DELETED, {"quantity": 1}, None, ENTITY_ITEM, "4", None),
        OrderFieldChange("quantity", 1, 2, ENTITY_ITEM, "5", "XYZ"),
        OrderFieldChange("weight", 1, 2, ENTITY_ITEM, "6", None),
        OrderFieldChange("order_notes", None, "Ring twice", ENTITY_NOTE, "COSTUMER"),
    ]

    assert label_order_changes(changes) == [
        "New item ABC-1",
        "Removed item #4",
        "XYZ quantity",
        "Item #6 weight",
        "Customer note",
    ]


def test_labels_unknown_fields_by_humanizing_them():
    assert label_order_changes([OrderFieldChange("some_new_field", 1, 2)]) == ["Some new field"]


def test_replacements_only_skips_first_time_fills():
    rows = [
        SimpleNamespace(field_name="client_email", from_value=None, to_value="a@x.com",
                        entity_type="order", entity_id=None, entity_label=None),
        SimpleNamespace(field_name="client_last_name", from_value="Doe", to_value="Roe",
                        entity_type="order", entity_id=None, entity_label=None),
    ]

    assert label_order_changes(rows, replacements_only=True) == ["Last name"]
    assert label_order_changes(rows) == ["Email", "Last name"]


def test_summarize_change_labels_truncates_past_the_limit():
    assert summarize_change_labels([]) is None
    assert summarize_change_labels(["Email"]) == "Email"
    assert summarize_change_labels(["Email", "Address"]) == "Email and Address"
    assert (
        summarize_change_labels(["Email", "Address", "Phone", "Note"])
        == "Email, Address and 2 more"
    )
