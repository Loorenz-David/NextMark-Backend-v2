from Delivery_app_BK.models import Order, db
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import get_route_freshness_updated_at
from Delivery_app_BK.services.domain.order.order_events import OrderEvent as StoredOrderEventName
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ORDER_CREATED,
    BUSINESS_EVENT_ORDER_STATE_CHANGED,
    BUSINESS_EVENT_ORDER_UPDATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.notifications import notify_order_event
from Delivery_app_BK.sockets.emitters.route_orders import emit_route_order_event, resolve_route_ids_for_order
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room

ORDER_REALTIME_EVENT_BY_NAME = {
    StoredOrderEventName.CREATED.value: BUSINESS_EVENT_ORDER_CREATED,
    StoredOrderEventName.EDITED.value: BUSINESS_EVENT_ORDER_UPDATED,
    StoredOrderEventName.DELIVERY_WINDOW_RESCHEDULED_BY_USER.value: BUSINESS_EVENT_ORDER_UPDATED,
    StoredOrderEventName.DELIVERY_PLAN_CHANGED.value: BUSINESS_EVENT_ORDER_UPDATED,
    StoredOrderEventName.DELIVERY_RESCHEDULED.value: BUSINESS_EVENT_ORDER_UPDATED,
    StoredOrderEventName.STATUS_CHANGED.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.CONFIRMED.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.PREPARING.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.READY.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.PROCESSING.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.COMPLETED.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.FAIL.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
    StoredOrderEventName.CANCELLED.value: BUSINESS_EVENT_ORDER_STATE_CHANGED,
}


def fanout_order_event(event_row) -> None:
    realtime_event_name = ORDER_REALTIME_EVENT_BY_NAME.get(event_row.event_name)
    if not realtime_event_name or not event_row.team_id:
        return

    order = db.session.get(Order, event_row.order_id) if event_row.order_id else None
    route_freshness_updated_at = get_route_freshness_updated_at(getattr(order, "route_plan", None)) if order else None
    payload = {
        "order_id": event_row.order_id,
        "actor_id": event_row.actor_id,
        "original_event_name": event_row.event_name,
        **(event_row.payload or {}),
    }
    if route_freshness_updated_at is not None:
        payload["route_freshness_updated_at"] = route_freshness_updated_at

    route_ids = resolve_route_ids_for_order(event_row.order_id, event_row.team_id)
    driver_event_name = (
        BUSINESS_EVENT_ORDER_CREATED
        if event_row.event_name == StoredOrderEventName.CONFIRMED.value and route_ids
        else realtime_event_name
    )

    envelope = build_business_event_envelope(
        event_id=event_row.event_id or f"order-event:{event_row.id}",
        event_name=realtime_event_name,
        occurred_at=event_row.occurred_at,
        team_id=event_row.team_id,
        entity_type="order",
        entity_id=event_row.order_id,
        payload=payload,
    )

    emit_business_event(
        room=build_team_admin_room(event_row.team_id),
        envelope=envelope,
    )
    emit_route_order_event(
        route_ids=route_ids,
        envelope=(
            envelope
            if driver_event_name == realtime_event_name
            else {
                **envelope,
                "event_name": driver_event_name,
            }
        ),
    )
    notify_order_event(
        event_id=envelope["event_id"],
        event_name=realtime_event_name,
        driver_event_name=driver_event_name,
        team_id=event_row.team_id,
        order_id=event_row.order_id,
        payload=payload,
        occurred_at=event_row.occurred_at,
        actor=event_row.actor,
    )
