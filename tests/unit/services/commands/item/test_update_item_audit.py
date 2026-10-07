import importlib
from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.audit import (
    FIELD_CREATED,
    FIELD_DELETED,
    snapshot_item_audit_values,
)

module = importlib.import_module("Delivery_app_BK.services.commands.item.update.update_item")


def _item(**overrides):
    values = {
        "id": 9,
        "order_id": 1,
        "article_number": "SKU-9",
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


def test_field_edit_is_recorded_on_the_items_order():
    item = _item()
    before = snapshot_item_audit_values(item)
    item.quantity = 4
    changes_by_order_id: dict = {}

    module._collect_item_audit_changes(
        changes_by_order_id, item=item, previous_order_id=1, audit_before=before
    )

    assert list(changes_by_order_id) == [1]
    assert [(c.field_name, c.from_value, c.to_value) for c in changes_by_order_id[1]] == [
        ("quantity", 1, 4)
    ]


def test_moving_an_item_records_removal_and_addition_on_each_order():
    item = _item()
    before = snapshot_item_audit_values(item)
    item.order_id = 2
    changes_by_order_id: dict = {}

    module._collect_item_audit_changes(
        changes_by_order_id, item=item, previous_order_id=1, audit_before=before
    )

    assert [c.field_name for c in changes_by_order_id[1]] == [FIELD_DELETED]
    assert [c.field_name for c in changes_by_order_id[2]] == [FIELD_CREATED]
    assert changes_by_order_id[1][0].from_value == before
