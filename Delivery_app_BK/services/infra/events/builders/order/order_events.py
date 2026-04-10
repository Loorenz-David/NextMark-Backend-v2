from datetime import datetime

from Delivery_app_BK.models import DeliveryPlan, Order
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.domain.order.order_states import (
    OrderState as OrderStateDomain,
)


ORDER_STATE_EVENT_BY_NAME = {
    OrderStateDomain.DRAFT.value: OrderEvent.CREATED.value,
    OrderStateDomain.CONFIRMED.value: OrderEvent.CONFIRMED.value,
    OrderStateDomain.PREPARING.value: OrderEvent.PREPARING.value,
    OrderStateDomain.READY.value: OrderEvent.READY.value,
    OrderStateDomain.PROCESSING.value: OrderEvent.PROCESSING.value,
    OrderStateDomain.COMPLETED.value: OrderEvent.COMPLETED.value,
    OrderStateDomain.CANCELLED.value: OrderEvent.CANCELLED.value,
    OrderStateDomain.FAIL.value: OrderEvent.FAIL.value,
}


def build_order_created_event(order_instance: Order) -> dict:
    payload = {
        "order_state_id": order_instance.order_state_id,
        "order_plan_objective": order_instance.order_plan_objective,
    }
    if order_instance.delivery_plan_id:
        payload["delivery_plan_id"] = order_instance.delivery_plan_id

    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.CREATED.value,
        "payload": payload,
    }


def build_order_edited_event(
    order_instance: Order,
    *,
    changed_sections: list[str] | None = None,
) -> dict:
    payload = {}
    if changed_sections:
        payload["changed_sections"] = changed_sections

    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.EDITED.value,
        "payload": payload,
    }


def build_delivery_window_rescheduled_by_user_event(
    order_instance: Order,
    old_earliest: datetime | None,
    old_latest: datetime | None,
    new_earliest: datetime | None,
    new_latest: datetime | None,
    *,
    changed_sections: list[str] | None = None,
) -> dict:
    payload = {
        "old_window_start": old_earliest.isoformat() if old_earliest else None,
        "old_window_end": old_latest.isoformat() if old_latest else None,
        "new_window_start": new_earliest.isoformat() if new_earliest else None,
        "new_window_end": new_latest.isoformat() if new_latest else None,
    }
    if changed_sections:
        payload["changed_sections"] = changed_sections

    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_WINDOW_RESCHEDULED_BY_USER.value,
        "payload": payload,
    }


def build_delivery_plan_changed_event(
    order_instance: Order,
    old_plan_id: int | None,
    new_plan: DeliveryPlan,
) -> dict:
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_PLAN_CHANGED.value,
        "payload": {
            "old_delivery_plan_id": old_plan_id,
            "new_delivery_plan_id": new_plan.id,
            "new_plan_type": new_plan.plan_type,
        },
    }


def build_order_status_changed_event(
    order_instance: Order,
    old_state_id: int,
    state_instance,
) -> dict:
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.STATUS_CHANGED.value,
        "payload": {
            "old_order_state_id": old_state_id,
            "new_order_state_id": state_instance.id,
            "new_order_state_name": state_instance.name,
        },
    }


def build_order_state_lifecycle_event(order_instance: Order, state_instance) -> dict | None:
    state_name = (state_instance.name or "").strip()
    event_name = ORDER_STATE_EVENT_BY_NAME.get(state_name, OrderEvent.FAIL.value)
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": event_name,
        "payload": {"order_state_id": state_instance.id},
    }


def build_delivery_rescheduled_event(
    order_instance: Order,
    *,
    old_plan_start: datetime | None,
    old_plan_end: datetime | None,
    new_plan_start: datetime | None,
    new_plan_end: datetime | None,
    reason: str = "plan_window_changed",
) -> dict:
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_RESCHEDULED.value,
        "payload": {
            "old_plan_start": old_plan_start.isoformat() if old_plan_start else None,
            "old_plan_end": old_plan_end.isoformat() if old_plan_end else None,
            "new_plan_start": new_plan_start.isoformat() if new_plan_start else None,
            "new_plan_end": new_plan_end.isoformat() if new_plan_end else None,
            "reason": reason,
        },
    }


def build_route_plan_changed_event(
    order_instance: Order,
    old_plan_id: int | None,
    new_plan,
) -> dict:
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_PLAN_CHANGED.value,
        "payload": {
            "old_delivery_plan_id": old_plan_id,
            "new_delivery_plan_id": new_plan.id if new_plan else None,
        },
    }


def build_order_state_transition_events(
    order_instance: Order,
    old_state_id: int,
    state_instance,
) -> list[dict]:
    if old_state_id == state_instance.id:
        return []

    events = [
        build_order_status_changed_event(
            order_instance=order_instance,
            old_state_id=old_state_id,
            state_instance=state_instance,
        )
    ]
    lifecycle_event = build_order_state_lifecycle_event(order_instance, state_instance)
    if lifecycle_event:
        events.append(lifecycle_event)

    return events
