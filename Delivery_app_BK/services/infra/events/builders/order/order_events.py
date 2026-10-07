from datetime import datetime
from uuid import uuid4

from Delivery_app_BK.models import DeliveryPlan, Order
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    normalize_order_plan_objective,
)
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
    audit_event_id: str | None = None,
) -> dict:
    """`audit_event_id` points at a sibling event that owns this edit's audit
    rows (a client form submission), so readers of the edit can find them."""
    payload = {}
    if changed_sections:
        payload["changed_sections"] = changed_sections
    if audit_event_id:
        payload["audit_event_id"] = audit_event_id

    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.EDITED.value,
        "payload": payload,
    }


def build_client_form_submitted_event(order_instance: Order) -> dict:
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.CLIENT_FORM_SUBMITTED.value,
        "payload": {},
    }


def mark_client_form_submission(
    event: dict,
    *,
    submission_source: str,
    relayed_by_user_id: int | None,
) -> dict:
    """Attribute an event to the customer rather than the staff session that
    relayed their form: no actor, and the relaying user kept in the payload."""
    event["actor_id"] = None
    event["payload"] = {
        **(event.get("payload") or {}),
        "submission_source": submission_source,
        "relayed_by_user_id": relayed_by_user_id,
    }
    return event


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
    new_plan_type = normalize_order_plan_objective(order_instance.order_plan_objective)
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_PLAN_CHANGED.value,
        "payload": {
            "old_delivery_plan_id": old_plan_id,
            "new_delivery_plan_id": new_plan.id,
            "new_plan_type": new_plan_type,
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
    old_plan_start: datetime | None = None,
    old_plan_end: datetime | None = None,
    new_plan_start: datetime | None = None,
    new_plan_end: datetime | None = None,
    old_expected_arrival: datetime | None = None,
    new_expected_arrival: datetime | None = None,
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
            "old_expected_arrival": old_expected_arrival.isoformat() if old_expected_arrival else None,
            "new_expected_arrival": new_expected_arrival.isoformat() if new_expected_arrival else None,
            "reason": reason,
        },
    }


def build_order_arrival_changed_event(
    order_instance: Order,
    *,
    old_expected_arrival: datetime,
    new_expected_arrival: datetime,
    cause: str,
) -> dict:
    """History entry for an arrival that moved within the order's route;
    `cause` names the route action (e.g. "stops_reordered")."""
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.ARRIVAL_CHANGED.value,
        "payload": {
            "old_expected_arrival": old_expected_arrival.isoformat(),
            "new_expected_arrival": new_expected_arrival.isoformat(),
            "cause": cause,
        },
    }


def build_route_plan_changed_event(
    order_instance: Order,
    old_plan_id: int | None,
    new_plan,
) -> dict:
    new_plan_id = new_plan.id if new_plan else None
    new_date_strategy = getattr(new_plan, "date_strategy", None) if new_plan else None
    return {
        "order_id": order_instance.id,
        "team_id": order_instance.team_id,
        "event_name": OrderEvent.DELIVERY_PLAN_CHANGED.value,
        "payload": {
            "old_delivery_plan_id": old_plan_id,
            "new_delivery_plan_id": new_plan_id,
            "old_route_plan_id": old_plan_id,
            "new_route_plan_id": new_plan_id,
            "new_plan_type": normalize_order_plan_objective(
                getattr(order_instance, "order_plan_objective", None)
            )
            or new_date_strategy,
            "new_date_strategy": new_date_strategy,
        },
    }


def fold_into_plan_change_notification(events: list[dict]) -> list[dict]:
    """One notification per order for a plan move.

    Scheduling an order emits several events — the plan change, the delivery
    reschedule and, for a draft, its confirmation. Each stays in the history
    (and may send customer messages), but only the plan change notifies: the
    others point at it, and it carries their status change and dates.
    """
    lead_by_order_id: dict[int, dict] = {}
    for event in events:
        if (
            event.get("event_name") == OrderEvent.DELIVERY_PLAN_CHANGED.value
            and event.get("order_id") not in lead_by_order_id
        ):
            event.setdefault("event_id", str(uuid4()))
            lead_by_order_id[event.get("order_id")] = event

    for event in events:
        lead = lead_by_order_id.get(event.get("order_id"))
        if lead is None or event is lead:
            continue
        payload = {
            **(event.get("payload") or {}),
            "notification_folded_into": lead["event_id"],
        }
        event["payload"] = payload
        if event.get("event_name") == OrderEvent.STATUS_CHANGED.value:
            lead["payload"] = {
                **(lead.get("payload") or {}),
                "notification_old_order_state_id": payload.get("old_order_state_id"),
                "notification_new_order_state_id": payload.get("new_order_state_id"),
            }
        elif event.get("event_name") == OrderEvent.DELIVERY_RESCHEDULED.value:
            # The delivery dates are what tells "scheduled for Oct 19" or
            # "rescheduled Oct 17 → Oct 19" apart from a plain plan move.
            lead["payload"] = {
                **(lead.get("payload") or {}),
                "notification_old_plan_start": payload.get("old_plan_start"),
                "notification_old_plan_end": payload.get("old_plan_end"),
                "notification_new_plan_start": payload.get("new_plan_start"),
                "notification_new_plan_end": payload.get("new_plan_end"),
            }

    return events


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
