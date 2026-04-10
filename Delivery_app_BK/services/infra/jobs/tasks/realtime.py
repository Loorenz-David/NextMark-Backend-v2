from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from Delivery_app_BK.models import (
    AppEventOutbox,
    OrderEvent,
    db,
)
from Delivery_app_BK.services.infra.jobs import with_app_context
from Delivery_app_BK.sockets.emitters.app_events import fanout_app_event
from Delivery_app_BK.sockets.emitters.order_events import fanout_order_event


@with_app_context
def relay_order_event_job(event_row_id: int) -> None:
    event_row = db.session.get(OrderEvent, event_row_id)
    if event_row is None:
        current_app.logger.warning("OrderEvent not found: %d", event_row_id)
        return
    
    # Skip if already relayed (idempotency check)
    if event_row.relayed_at is not None:
        current_app.logger.debug("Event already relayed (idempotency): %d", event_row_id)
        return
    
    try:
        fanout_order_event(event_row)
        
        # Mark as relayed for idempotency
        event_row.relayed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as exc:
        current_app.logger.error(
            "Failed to relay OrderEvent %d: %s",
            event_row_id, str(exc), exc_info=True
        )
        raise


@with_app_context
def relay_app_event_job(event_row_id: int) -> None:
    event_row = db.session.get(AppEventOutbox, event_row_id)
    if event_row is None:
        current_app.logger.warning("AppEventOutbox not found: %d", event_row_id)
        return
    
    # Skip if already relayed (idempotency check)
    if event_row.relayed_at is not None:
        current_app.logger.debug("Event already relayed (idempotency): %d", event_row_id)
        return
    
    try:
        fanout_app_event(event_row)
        
        # Mark as relayed for idempotency
        event_row.relayed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as exc:
        current_app.logger.error(
            "Failed to relay AppEventOutbox %d: %s",
            event_row_id, str(exc), exc_info=True
        )
        raise
