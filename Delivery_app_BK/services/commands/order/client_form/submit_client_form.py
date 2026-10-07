"""
Accept and persist the client-submitted info for an order.

Security:
- Token is hashed before lookup — raw token is never stored.
- Payload is strictly filtered to ALLOWED_CLIENT_FIELDS; any other keys are silently dropped.
- `accepted_terms_version_id` is deliberately outside that set — it is validated
  against the team's active terms version before being written.
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
from Delivery_app_BK.services.commands.order.client_form._resolve_terms_acceptance import (
    resolve_terms_acceptance,
)
from Delivery_app_BK.services.commands.order.client_form._validate_token import validate_and_get_order
from Delivery_app_BK.services.commands.order.update_extensions import (
    OrderUpdateChangeFlags,
    OrderUpdateDelta,
    apply_order_update_extensions,
    build_order_update_extension_context,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.audit import (
    diff_order_audit_values,
    snapshot_order_audit_values,
)
from Delivery_app_BK.services.infra.audit import (
    new_audit_event_id,
    record_order_audit_changes,
)
from Delivery_app_BK.services.infra.events.builders.order import (
    build_client_form_submitted_event,
    build_order_edited_event,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events

ALLOWED_CLIENT_FIELDS = {
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
    "marketing_messages"
}
AUDIT_FIELDS = (*sorted(ALLOWED_CLIENT_FIELDS), "order_notes")


def submit_client_form(token: str, payload: dict) -> dict:
    order = validate_and_get_order(token)
    note_payload = payload.get("order_notes") if isinstance(payload, dict) else None

    # Validated against the team's active version before anything is written.
    accepted_terms = resolve_terms_acceptance(order.team_id, payload)

    # Sanitize — only write allowed fields
    safe_payload = {k: v for k, v in payload.items() if k in ALLOWED_CLIENT_FIELDS}
    audit_before = snapshot_order_audit_values(order, fields=AUDIT_FIELDS)

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

    submitted_at = datetime.now(timezone.utc)
    order.client_form_submitted_at = submitted_at
    order.client_form_token_encrypted = None

    if accepted_terms is not None:
        order.accepted_terms_version_id = accepted_terms.id
        order.terms_accepted_at = submitted_at

    # The client is not a user, so the event and its audit rows carry no actor.
    system_ctx = ServiceContext(identity={"team_id": order.team_id, "active_team_id": order.team_id})
    # The customer's changes belong to their submission; the companion edit
    # event only carries the realtime "order updated" frame.
    submitted_event = build_client_form_submitted_event(order)
    submitted_event["event_id"] = new_audit_event_id()
    record_order_audit_changes(
        system_ctx,
        order_id=order.id,
        team_id=order.team_id,
        event_id=submitted_event["event_id"],
        changes=diff_order_audit_values(
            audit_before,
            snapshot_order_audit_values(order, fields=AUDIT_FIELDS),
        ),
    )

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
        system_ctx,
        [
            build_order_edited_event(
                order,
                changed_sections=["client_form_submission"],
            ),
            submitted_event,
        ],
    )

    return {"success": True}
