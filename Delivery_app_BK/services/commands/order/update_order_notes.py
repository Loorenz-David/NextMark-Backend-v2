from __future__ import annotations

import ast
import json
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Order, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.queries.get_instance import get_instance


EDITABLE_NOTE_TYPES = {"GENERAL", "COSTUMER"}
SUPPORTED_ACTIONS = {"update", "delete"}


def update_order_notes(ctx: ServiceContext, action: str) -> dict:
    if action not in SUPPORTED_ACTIONS:
        raise ValidationFailed(f"Unsupported order note action '{action}'.")

    payload = ctx.incoming_data or {}
    order = get_instance(
        ctx=ctx,
        model=Order,
        value=_validate_target_id(payload.get("target_id")),
    )
    note_payload = _validate_note_payload(payload.get("order_notes"))
    current_notes = _normalize_notes_list(getattr(order, "order_notes", None))

    if action == "update":
        updated_notes = _update_note(current_notes, note_payload)
    else:
        updated_notes = _delete_note(current_notes, note_payload)

    order.order_notes = updated_notes
    db.session.add(order)
    db.session.commit()

    emit_order_events(
        ctx,
        [
            build_order_edited_event(
                order,
                changed_sections=["details"],
            )
        ],
    )

    return {"order_notes": list(order.order_notes or [])}


def _validate_target_id(value: Any) -> int | str:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValidationFailed("target_id is required.")


def _validate_note_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationFailed("order_notes must be an object with keys: type, content.")

    note_type = value.get("type")
    content = value.get("content")

    if not isinstance(note_type, str) or not note_type.strip():
        raise ValidationFailed("order_notes.type is required.")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise ValidationFailed("order_notes.content must be a string when provided.")

    return {
        "type": note_type.strip(),
        "content": content,
    }


def _normalize_notes_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for note in value:
        parsed = _parse_note_like_value(note)
        if parsed is not None:
            normalized.append(parsed)
    return normalized


def _parse_note_like_value(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(stripped)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _update_note(notes: list[dict[str, Any]], note_payload: dict[str, Any]) -> list[dict[str, Any]]:
    note_type = note_payload["type"]
    if note_type not in EDITABLE_NOTE_TYPES:
        raise ValidationFailed(
            f"order_notes.type must be one of {sorted(EDITABLE_NOTE_TYPES)} for note updates."
        )

    updated = False
    next_notes: list[dict[str, Any]] = []
    for note in notes:
        if isinstance(note, dict) and note.get("type") == note_type and not updated:
            next_note = dict(note)
            next_note["content"] = note_payload["content"]
            next_notes.append(next_note)
            updated = True
            continue
        next_notes.append(note)

    if not updated:
        raise ValidationFailed(f"No order note found for type '{note_type}'.")

    return next_notes


def _delete_note(notes: list[dict[str, Any]], note_payload: dict[str, Any]) -> list[dict[str, Any]]:
    note_type = note_payload["type"]
    note_content = note_payload["content"]

    deleted = False
    next_notes: list[dict[str, Any]] = []
    for note in notes:
        if (
            not deleted
            and isinstance(note, dict)
            and note.get("type") == note_type
            and note.get("content", "") == note_content
        ):
            deleted = True
            continue
        next_notes.append(note)

    if not deleted:
        raise ValidationFailed("No matching order note found for deletion.")

    return next_notes
