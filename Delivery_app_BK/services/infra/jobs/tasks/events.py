from __future__ import annotations

from Delivery_app_BK.models import (
    AppEventOutbox,
    OrderEvent,
    RoutePlanEvent,
    db,
)
from Delivery_app_BK.services.infra.events import get_event_bus
from Delivery_app_BK.services.infra.jobs import with_app_context
from Delivery_app_BK.services.infra.jobs.realtime import (
    enqueue_app_realtime_relay,
    enqueue_order_realtime_relay,
)


@with_app_context
def process_order_event_job(event_row_id: int) -> None:
    event_row = db.session.get(OrderEvent, event_row_id)
    if event_row is None:
        return

    get_event_bus().publish(event_row)
    enqueue_order_realtime_relay(event_row.id)


@with_app_context
def process_route_plan_event_job(event_row_id: int) -> None:
    event_row = db.session.get(RoutePlanEvent, event_row_id)
    if event_row is None:
        return

    get_event_bus().publish(event_row)


@with_app_context
def process_app_event_outbox_job(event_row_id: int) -> None:
    event_row = db.session.get(AppEventOutbox, event_row_id)
    if event_row is None:
        return

    enqueue_app_realtime_relay(event_row.id)
