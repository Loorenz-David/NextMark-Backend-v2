from Delivery_app_BK.models import OrderCase
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ORDER_CASE_CREATED,
    BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED,
    BUSINESS_EVENT_ORDER_CASE_UPDATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.emitters.route_orders import emit_route_order_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room


def _emit_order_case_event(order_case: OrderCase, *, event_name: str, payload: dict | None = None) -> None:
    team_id = order_case.order.team_id if order_case.order else None
    if team_id is None:
        return

    envelope = build_business_event_envelope(
        event_name=event_name,
        occurred_at=order_case.creation_date,
        team_id=team_id,
        entity_type="order_case",
        entity_id=order_case.id,
        payload={
            "order_case_id": order_case.id,
            "order_case_client_id": order_case.client_id,
            "order_id": order_case.order_id,
            "state": order_case.state,
            **(payload or {}),
        },
    )

    emit_business_event(
        room=build_team_admin_room(team_id),
        envelope=envelope,
    )
    emit_route_order_event(
        team_id=team_id,
        order_id=order_case.order_id,
        envelope=envelope,
    )


def emit_order_case_created(order_case: OrderCase) -> None:
    _emit_order_case_event(order_case, event_name=BUSINESS_EVENT_ORDER_CASE_CREATED)


def emit_order_case_updated(order_case: OrderCase, *, changed_fields: list[str] | None = None) -> None:
    _emit_order_case_event(
        order_case,
        event_name=BUSINESS_EVENT_ORDER_CASE_UPDATED,
        payload={"changed_fields": changed_fields or []},
    )


def emit_order_case_state_changed(order_case: OrderCase) -> None:
    _emit_order_case_event(order_case, event_name=BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED)
