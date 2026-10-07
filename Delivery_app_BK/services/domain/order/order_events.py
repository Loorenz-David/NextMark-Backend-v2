from enum import Enum
from typing import Any


class OrderEvent(str, Enum):
    CREATED = "order_created"
    CONFIRMED = "order_confirmed"
    PREPARING = "order_preparing"
    EDITED = "order_edited"
    READY = "order_ready"
    PROCESSING = "order_processing"
    COMPLETED = "order_completed"
    FAIL = "order_failed"
    CANCELLED = "order_cancelled"
    STATUS_CHANGED = "order_status_changed"
    DELIVERY_WINDOW_RESCHEDULED_BY_USER = "order_delivery_window_changed_by_user"
    DELIVERY_PLAN_CHANGED = "order_delivery_plan_changed"
    DELIVERY_RESCHEDULED = "order_rescheduled"
    CLIENT_FORM_LINK_SENT = "client_form_link_sent"
    CLIENT_FORM_SUBMITTED = "client_form_submitted"


# `changed_sections` values with meaning beyond display: an edit carrying
# CUSTOMER changed the customer's identity fields and is pushed to Shopify; one
# carrying CLIENT_FORM_SUBMISSION is the customer's own form, whose companion
# CLIENT_FORM_SUBMITTED event does that push instead.
ORDER_EDIT_SECTION_CUSTOMER = "customer"
ORDER_EDIT_SECTION_CLIENT_FORM = "client_form_submission"

# A form the customer filled on a staff member's linked device. The staff app
# relays it, but the data and the act of submitting are the customer's.
CLIENT_FORM_SOURCE_LINKED_DEVICE = "linked_device"
CLIENT_FORM_SUBMISSION_SOURCES = frozenset({CLIENT_FORM_SOURCE_LINKED_DEVICE})


ORDER_EVENT_ORIGIN_USER = "user"
ORDER_EVENT_ORIGIN_CLIENT = "client"
ORDER_EVENT_ORIGIN_SYSTEM = "system"


def resolve_order_event_origin(
    event_name: str,
    payload: dict[str, Any] | None,
    actor_id: int | None,
) -> str:
    """Who an order event is attributed to. The customer's form — public link
    or relayed from a linked device — is the client's even when a staff session
    carried it; otherwise an event with an actor is that user's, and the rest
    (integrations, background jobs) is the system's."""
    payload = payload or {}
    changed_sections = payload.get("changed_sections") or []
    if (
        event_name == OrderEvent.CLIENT_FORM_SUBMITTED.value
        or ORDER_EDIT_SECTION_CLIENT_FORM in changed_sections
        or payload.get("submission_source") in CLIENT_FORM_SUBMISSION_SOURCES
    ):
        return ORDER_EVENT_ORIGIN_CLIENT
    if actor_id is not None:
        return ORDER_EVENT_ORIGIN_USER
    return ORDER_EVENT_ORIGIN_SYSTEM


class OrderEventPrintDocuments(str,Enum):
    CREATED = OrderEvent.CREATED.value
    CONFIRMED = OrderEvent.CONFIRMED.value
    EDITED = OrderEvent.EDITED.value


"""
Delivery plan changed happes when a order changes of delivery plan type, 

Order_rescheduled happens when a delivery plan changes it's dates, when an order moves
from no plan into a delivery plan, or when an order changes plan and dates are not the
same as the previous plan dates.

DELIVERY_WINDOW_RESCHEDULED_BY_USER happens when a user changes the window of an order manually,
this windows are bounderies not clear dates 


"""
