from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app
from pydantic import ValidationError, BaseModel

from Delivery_app_BK.services.domain.user import ADMIN_APP_SCOPE, DRIVER_APP_SCOPE
from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.notifications import build_realtime_notification_preview
from Delivery_app_BK.sockets.contracts.realtime import (
    DEFAULT_EVENT_VERSION,
    SERVER_EVENT_REALTIME_EVENT,
)


class BusinessEventEnvelope(BaseModel):
    """Schema for business event envelopes sent to clients."""
    event_id: str
    event_name: str
    version: str
    occurred_at: str
    team_id: int | None
    entity_type: str
    entity_id: int | None
    app_scopes: list[str]
    payload: dict


def build_business_event_envelope(
    *,
    event_name: str,
    team_id: int | None,
    entity_type: str,
    entity_id: int | None,
    payload: dict | None,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
    app_scopes: list[str] | None = None,
) -> dict:
    resolved_occurred_at = occurred_at or datetime.now(timezone.utc)
    resolved_version = str(DEFAULT_EVENT_VERSION)

    envelope = {
        "event_id": event_id or str(uuid4()),
        "event_name": event_name,
        "version": resolved_version,
        "occurred_at": resolved_occurred_at.isoformat(),
        "team_id": team_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "app_scopes": app_scopes or [ADMIN_APP_SCOPE, DRIVER_APP_SCOPE],
        "payload": payload or {},
    }
    
    # Validate envelope schema
    try:
        BusinessEventEnvelope(**envelope)
    except ValidationError as e:
        current_app.logger.error(
            "Invalid event envelope: event_name=%s, error=%s",
            event_name, str(e)
        )
        raise
    
    return envelope


def emit_business_event(*, room: str, envelope: dict) -> None:
    """Emit event to room via Socket.IO with validation."""
    try:
        payload = envelope.get("payload")
        if isinstance(payload, dict) and "notification_preview" not in payload:
            payload = {
                **payload,
                "notification_preview": build_realtime_notification_preview(
                    event_name=str(envelope.get("event_name") or ""),
                    entity_type=str(envelope.get("entity_type") or ""),
                    entity_id=envelope.get("entity_id") if isinstance(envelope.get("entity_id"), int) else None,
                    payload=payload,
                ),
            }
            envelope = {
                **envelope,
                "payload": payload,
            }

        socketio.emit(SERVER_EVENT_REALTIME_EVENT, envelope, room=room)
        current_app.logger.debug(
            "Event emitted to room: room=%s, event=%s, entity=%s:%s",
            room, envelope.get("event_name"), envelope.get("entity_type"), envelope.get("entity_id")
        )
    except Exception as exc:
        current_app.logger.error(
            "Failed to emit event to room %s: %s",
            room, str(exc), exc_info=True
        )
        raise
