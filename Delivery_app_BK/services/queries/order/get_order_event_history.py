from sqlalchemy.orm import selectinload

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Order, OrderEvent, db

from ...context import ServiceContext


def _serialize_action(action) -> dict:
    return {
        "id": action.id,
        "event_id": action.event_id,
        "team_id": action.team_id,
        "action_name": action.action_name,
        "action_scope": action.action_scope,
        "payload": action.payload or {},
        "status": action.status,
        "attempts": action.attempts,
        "last_error": action.last_error,
        "scheduled_for": action.scheduled_for.isoformat() if action.scheduled_for else None,
        "enqueued_at": action.enqueued_at.isoformat() if action.enqueued_at else None,
        "processed_at": action.processed_at.isoformat() if action.processed_at else None,
        "schedule_anchor_type": action.schedule_anchor_type,
        "schedule_anchor_at": action.schedule_anchor_at.isoformat() if action.schedule_anchor_at else None,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }


def _serialize_event(event) -> dict:
    sorted_actions = sorted(
        list(event.actions or []),
        key=lambda row: (row.created_at or row.updated_at, row.id),
        reverse=True,
    )

    return {
        "id": event.id,
        "event_id": event.event_id,
        "order_id": event.order_id,
        "team_id": event.team_id,
        "actor_id": event.actor_id,
        "event_name": event.event_name,
        "payload": event.payload or {},
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "entity_version": event.entity_version,
        "dispatch_status": event.dispatch_status,
        "dispatch_attempts": event.dispatch_attempts,
        "claimed_at": event.claimed_at.isoformat() if event.claimed_at else None,
        "claimed_by": event.claimed_by,
        "next_attempt_at": event.next_attempt_at.isoformat() if event.next_attempt_at else None,
        "last_error": event.last_error,
        "relayed_at": event.relayed_at.isoformat() if event.relayed_at else None,
        "actions": [_serialize_action(action) for action in sorted_actions],
    }


def get_order_event_history(order_id: int, ctx: ServiceContext) -> dict:
    order_query = db.session.query(Order)
    if ctx.team_id:
        order_query = order_query.filter(Order.team_id == ctx.team_id)
    order = order_query.filter(Order.id == order_id).first()

    if order is None:
        raise NotFound(f"Order with id: {order_id} does not exist.")

    event_query = db.session.query(OrderEvent).options(selectinload(OrderEvent.actions))
    if ctx.team_id:
        event_query = event_query.filter(OrderEvent.team_id == ctx.team_id)

    events = (
        event_query
        .filter(OrderEvent.order_id == order_id)
        .order_by(OrderEvent.occurred_at.desc(), OrderEvent.id.desc())
        .all()
    )

    return {
        "order_id": order_id,
        "order_events": [_serialize_event(event) for event in events],
    }
