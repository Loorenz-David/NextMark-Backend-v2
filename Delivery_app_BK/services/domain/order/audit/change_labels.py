from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .changes import (
    ENTITY_ITEM,
    ENTITY_NOTE,
    FIELD_CREATED,
    FIELD_DELETED,
    is_blank_audit_value,
)

ORDER_FIELD_LABELS: dict[str, str] = {
    "order_plan_objective": "Plan type",
    "operation_type": "Operation",
    "reference_number": "Reference",
    "external_order_id": "External order ID",
    "external_source": "External source",
    "external_tracking_number": "Tracking number",
    "external_tracking_link": "Tracking link",
    "client_first_name": "First name",
    "client_last_name": "Last name",
    "client_email": "Email",
    "client_primary_phone": "Primary phone",
    "client_secondary_phone": "Secondary phone",
    "client_address": "Address",
    "help_to_carry": "Help to carry",
    "marketing_messages": "Marketing messages",
    "delivery_windows": "Delivery window",
}

ITEM_FIELD_LABELS: dict[str, str] = {
    "article_number": "article",
    "reference_number": "reference",
    "item_type": "type",
    "quantity": "quantity",
    "weight": "weight",
    "dimension_depth": "depth",
    "dimension_height": "height",
    "dimension_width": "width",
    "properties": "properties",
    "item_position": "position",
    "item_state_id": "state",
    "page_link": "page link",
}

NOTE_TYPE_LABELS: dict[str, str] = {
    "GENERAL": "General note",
    "COSTUMER": "Customer note",
    "FAILURE": "Failure note",
}


def label_order_changes(
    changes: Iterable[Any],
    *,
    replacements_only: bool = False,
) -> list[str]:
    """Distinct human labels for audit changes, in the order they were recorded.

    `changes` are audit rows or `OrderFieldChange`s. With `replacements_only`,
    first-time fills are skipped — a customer completing an empty field is not
    a correction worth calling out.
    """
    labels: list[str] = []
    for change in changes:
        if replacements_only and is_blank_audit_value(getattr(change, "from_value", None)):
            continue
        label = _label_change(change)
        if label not in labels:
            labels.append(label)
    return labels


def summarize_change_labels(labels: list[str], *, limit: int = 2) -> str | None:
    """"Email", "Email and Address", "Email, Address and 2 more"."""
    if not labels:
        return None
    if len(labels) == 1:
        return labels[0]
    if len(labels) <= limit:
        return f"{', '.join(labels[:-1])} and {labels[-1]}"
    shown = labels[:limit]
    return f"{', '.join(shown)} and {len(labels) - limit} more"


def _label_change(change: Any) -> str:
    entity_type = getattr(change, "entity_type", None)
    field_name = getattr(change, "field_name", "") or ""

    if entity_type == ENTITY_ITEM:
        reference = _item_reference(change)
        if field_name == FIELD_CREATED:
            return f"New item {reference}".rstrip()
        if field_name == FIELD_DELETED:
            return f"Removed item {reference}".rstrip()
        item = reference if reference and not reference.startswith("#") else f"Item {reference}".rstrip()
        return f"{item} {ITEM_FIELD_LABELS.get(field_name, _humanize(field_name).lower())}"

    if entity_type == ENTITY_NOTE:
        note_type = getattr(change, "entity_id", None) or "GENERAL"
        return NOTE_TYPE_LABELS.get(note_type, f"{_humanize(note_type)} note")

    return ORDER_FIELD_LABELS.get(field_name, _humanize(field_name))


def _item_reference(change: Any) -> str:
    """The item's label, else `#<id>`, else empty."""
    label = getattr(change, "entity_label", None)
    if isinstance(label, str) and label.strip():
        return label.strip()
    entity_id = getattr(change, "entity_id", None)
    return f"#{entity_id}" if entity_id else ""


def _humanize(value: str) -> str:
    spaced = value.replace("_", " ").strip().lower()
    return spaced[:1].upper() + spaced[1:]
