from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from Delivery_app_BK.models import AppEventOutbox, db
from Delivery_app_BK.services.context import ServiceContext


def emit_app_events(ctx: ServiceContext, events: Iterable[dict]) -> list[AppEventOutbox]:
    actor_id = ctx.user_id if ctx.user_id else None
    rows: list[AppEventOutbox] = []

    for event in events:
        event_name = event.get("event_name")
        entity_type = event.get("entity_type")
        entity_id = event.get("entity_id")
        if not event_name or not entity_type or entity_id is None:
            continue

        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        row = AppEventOutbox(
            event_id=event.get("event_id", str(uuid4())),
            event_name=event_name,
            payload=payload,
            actor_id=event.get("actor_id", actor_id),
            team_id=event.get("team_id", ctx.team_id),
            entity_type=str(entity_type),
            entity_id=str(entity_id),
            entity_version=event.get("entity_version"),
            occurred_at=event.get("occurred_at") or datetime.now(timezone.utc),
            dispatch_status=(
                AppEventOutbox.DISPATCH_STATUS_DISPATCHED
                if ctx.prevent_event_bus
                else AppEventOutbox.DISPATCH_STATUS_PENDING
            ),
            dispatch_attempts=0,
            next_attempt_at=event.get("next_attempt_at") or datetime.now(timezone.utc),
        )
        db.session.add(row)
        rows.append(row)

    if not rows:
        return []

    db.session.flush()
    db.session.commit()
    return rows
