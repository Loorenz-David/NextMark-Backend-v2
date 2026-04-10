"""
Accept and persist the client-submitted info for an order.

Security:
- Token is hashed before lookup — raw token is never stored.
- Payload is strictly filtered to ALLOWED_CLIENT_FIELDS; any other keys are silently dropped.
- Token is invalidated immediately on successful write (single-use).

Side effects:
- Emits an order event through the outbox so realtime subscribers receive
    the standard business envelope (`realtime:event`).

Returns: { "success": True }
Raises: TokenInvalidError | TokenExpiredError | TokenAlreadyUsedError | ValidationError
"""

from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.services.commands.order.client_form._validate_token import validate_and_get_order
from Delivery_app_BK.services.commands.order.update_extensions import (
    OrderUpdateChangeFlags,
    OrderUpdateDelta,
    apply_order_update_extensions,
    build_order_update_extension_context,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events

ALLOWED_CLIENT_FIELDS = {
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
}


def submit_client_form(token: str, payload: dict) -> dict:
    order = validate_and_get_order(token)
    note_payload = payload.get("order_notes") if isinstance(payload, dict) else None

    # Sanitize — only write allowed fields
    safe_payload = {k: v for k, v in payload.items() if k in ALLOWED_CLIENT_FIELDS}

    for field, value in safe_payload.items():
        setattr(order, field, value)

    if note_payload is not None:
        if not isinstance(note_payload, dict):
            raise ValidationFailed("order_notes must be a note object with keys: type, content")
        current_notes = list(order.order_notes) if isinstance(getattr(order, "order_notes", None), list) else []
        if note_payload.get("type") == "COSTUMER":
            current_notes = [
                note
                for note in current_notes
                if not (isinstance(note, dict) and note.get("type") == "COSTUMER")
            ]
        current_notes.append(note_payload)
        order.order_notes = current_notes

    order.client_form_submitted_at = datetime.now(timezone.utc)
    order.client_form_token_encrypted = None
    db.session.commit()

    # If the customer updated the delivery address, recompute downstream stop ETAs
    # using the same extension machinery as update_order (intent-based: presence of
    # client_address key is sufficient, matching update_order semantics).
    if "client_address" in safe_payload:
        ctx = ServiceContext(identity={"team_id": order.team_id, "active_team_id": order.team_id})
        delta = OrderUpdateDelta(
            order_instance=order,
            old_values={},
            new_values={},
            flags=OrderUpdateChangeFlags(address_changed=True),
            delivery_plan=getattr(order, "delivery_plan", None),
        )
        ext_ctx = build_order_update_extension_context(ctx, [delta])
        ext_result = apply_order_update_extensions(ctx, [delta], ext_ctx)
        for action in ext_result.post_flush_actions:
            action()
        if ext_result.instances:
            db.session.add_all(ext_result.instances)
            db.session.commit()

    emit_order_events(
        ServiceContext(identity={"team_id": order.team_id, "active_team_id": order.team_id}),
        [
            build_order_edited_event(
                order,
                changed_sections=["client_form_submission"],
            )
        ],
    )

    return {"success": True}
