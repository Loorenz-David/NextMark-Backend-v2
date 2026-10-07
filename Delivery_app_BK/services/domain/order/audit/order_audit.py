from __future__ import annotations

import ast
import json
from collections import Counter
from typing import Any

from .changes import (
    ENTITY_NOTE,
    OrderFieldChange,
    audit_values_differ,
    to_audit_value,
)

AUDITED_ORDER_FIELDS: tuple[str, ...] = (
    "order_plan_objective",
    "operation_type",
    "reference_number",
    "external_order_id",
    "external_source",
    "external_tracking_number",
    "external_tracking_link",
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
    "help_to_carry",
    "marketing_messages",
)
DELIVERY_WINDOWS_FIELD = "delivery_windows"
ORDER_NOTES_FIELD = "order_notes"
DEFAULT_NOTE_TYPE = "GENERAL"


def snapshot_order_audit_values(
    order: Any,
    fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Capture the audited state of an order. ``fields`` narrows the scalar
    fields for paths that only touch a few columns; windows and notes are
    included only when ``fields`` is omitted or names them."""
    scalar_fields = AUDITED_ORDER_FIELDS if fields is None else tuple(
        field for field in fields if field in AUDITED_ORDER_FIELDS
    )
    snapshot = {
        field: to_audit_value(getattr(order, field, None))
        for field in scalar_fields
    }
    if fields is None or DELIVERY_WINDOWS_FIELD in fields:
        snapshot[DELIVERY_WINDOWS_FIELD] = _snapshot_delivery_windows(order)
    if fields is None or ORDER_NOTES_FIELD in fields:
        snapshot[ORDER_NOTES_FIELD] = normalize_audit_notes(
            getattr(order, ORDER_NOTES_FIELD, None)
        )
    return snapshot


def diff_order_audit_values(
    old: dict[str, Any],
    new: dict[str, Any],
) -> list[OrderFieldChange]:
    changes: list[OrderFieldChange] = []

    for field in AUDITED_ORDER_FIELDS:
        if field not in old and field not in new:
            continue
        old_value = old.get(field)
        new_value = new.get(field)
        if audit_values_differ(old_value, new_value):
            changes.append(OrderFieldChange(field, old_value, new_value))

    if DELIVERY_WINDOWS_FIELD in old or DELIVERY_WINDOWS_FIELD in new:
        old_windows = old.get(DELIVERY_WINDOWS_FIELD) or []
        new_windows = new.get(DELIVERY_WINDOWS_FIELD) or []
        if audit_values_differ(old_windows, new_windows):
            changes.append(
                OrderFieldChange(DELIVERY_WINDOWS_FIELD, old_windows, new_windows)
            )

    if ORDER_NOTES_FIELD in old or ORDER_NOTES_FIELD in new:
        changes.extend(
            diff_audit_notes(
                old.get(ORDER_NOTES_FIELD) or [],
                new.get(ORDER_NOTES_FIELD) or [],
            )
        )

    return changes


def normalize_audit_notes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    notes: list[dict[str, str]] = []
    for entry in value:
        parsed = _parse_note(entry)
        if parsed is None:
            continue
        note_type = parsed.get("type")
        content = parsed.get("content")
        notes.append(
            {
                "type": note_type.strip()
                if isinstance(note_type, str) and note_type.strip()
                else DEFAULT_NOTE_TYPE,
                "content": content if isinstance(content, str) else "",
            }
        )
    return notes


def diff_audit_notes(
    old_notes: list[dict[str, str]],
    new_notes: list[dict[str, str]],
) -> list[OrderFieldChange]:
    """Notes have no ids, so they are compared as a multiset of contents per
    note type. One removal paired with one addition of the same type reads as
    an edit; anything else is reported as separate additions and removals."""
    changes: list[OrderFieldChange] = []
    note_types = _ordered_note_types(old_notes, new_notes)

    for note_type in note_types:
        old_contents = Counter(
            note["content"] for note in old_notes if note["type"] == note_type
        )
        new_contents = Counter(
            note["content"] for note in new_notes if note["type"] == note_type
        )
        removed = list((old_contents - new_contents).elements())
        added = list((new_contents - old_contents).elements())

        if len(removed) == 1 and len(added) == 1:
            changes.append(_note_change(note_type, removed[0], added[0]))
            continue
        changes.extend(_note_change(note_type, content, None) for content in removed)
        changes.extend(_note_change(note_type, None, content) for content in added)

    return changes


def _note_change(note_type: str, old: str | None, new: str | None) -> OrderFieldChange:
    return OrderFieldChange(
        field_name=ORDER_NOTES_FIELD,
        from_value=old,
        to_value=new,
        entity_type=ENTITY_NOTE,
        entity_id=note_type,
        entity_label=note_type,
    )


def _ordered_note_types(*note_lists: list[dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for notes in note_lists:
        for note in notes:
            if note["type"] not in seen:
                seen.append(note["type"])
    return seen


def _parse_note(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    stripped = value.strip()
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(stripped)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return {"type": DEFAULT_NOTE_TYPE, "content": stripped}


def _snapshot_delivery_windows(order: Any) -> list[dict[str, Any]]:
    windows = list(getattr(order, DELIVERY_WINDOWS_FIELD, None) or [])
    snapshot = [
        {
            "start_at": to_audit_value(getattr(window, "start_at", None)),
            "end_at": to_audit_value(getattr(window, "end_at", None)),
            "window_type": getattr(window, "window_type", None),
        }
        for window in windows
    ]
    return sorted(
        snapshot,
        key=lambda window: (
            window["start_at"] or "",
            window["end_at"] or "",
            window["window_type"] or "",
        ),
    )
