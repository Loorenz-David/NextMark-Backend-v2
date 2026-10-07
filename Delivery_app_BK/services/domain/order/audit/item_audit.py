from __future__ import annotations

from typing import Any

from .changes import (
    ENTITY_ITEM,
    FIELD_CREATED,
    FIELD_DELETED,
    OrderFieldChange,
    audit_values_differ,
    to_audit_value,
)

AUDITED_ITEM_FIELDS: tuple[str, ...] = (
    "article_number",
    "reference_number",
    "item_type",
    "quantity",
    "weight",
    "dimension_depth",
    "dimension_height",
    "dimension_width",
    "properties",
    "item_position",
    "item_state_id",
    "page_link",
)


def snapshot_item_audit_values(item: Any) -> dict[str, Any]:
    return {
        field: to_audit_value(getattr(item, field, None))
        for field in AUDITED_ITEM_FIELDS
    }


def diff_item_audit_values(
    old: dict[str, Any],
    new: dict[str, Any],
    item: Any,
) -> list[OrderFieldChange]:
    return [
        _item_change(item, field, old.get(field), new.get(field))
        for field in AUDITED_ITEM_FIELDS
        if audit_values_differ(old.get(field), new.get(field))
    ]


def item_created_change(item: Any) -> OrderFieldChange:
    return _item_change(item, FIELD_CREATED, None, snapshot_item_audit_values(item))


def item_deleted_change(
    item: Any,
    snapshot: dict[str, Any] | None = None,
) -> OrderFieldChange:
    return _item_change(
        item,
        FIELD_DELETED,
        snapshot if snapshot is not None else snapshot_item_audit_values(item),
        None,
    )


def _item_change(item: Any, field: str, old: Any, new: Any) -> OrderFieldChange:
    item_id = getattr(item, "id", None)
    label = getattr(item, "article_number", None)
    return OrderFieldChange(
        field_name=field,
        from_value=old,
        to_value=new,
        entity_type=ENTITY_ITEM,
        entity_id=str(item_id) if item_id is not None else None,
        entity_label=label if isinstance(label, str) and label else None,
    )
