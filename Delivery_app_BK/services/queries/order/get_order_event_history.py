from sqlalchemy.orm import selectinload

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import ItemState, Order, OrderAuditLog, OrderEvent, User, UserRole, db
from Delivery_app_BK.services.domain.order.order_events import resolve_order_event_origin
from Delivery_app_BK.services.domain.user import resolve_user_role_id_for_team

from ...context import ServiceContext
from ..user import serialize_user_actor
from .serialize_order_audit_change import ITEM_STATE_FIELD, serialize_order_audit_change


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


def _serialize_actor(event, roles_by_id: dict[int, UserRole]) -> dict | None:
    actor = event.actor
    if actor is None:
        return None

    role_id = resolve_user_role_id_for_team(actor, event.team_id)
    return serialize_user_actor(actor, roles_by_id.get(role_id))


def _load_actor_roles(events: list) -> dict[int, UserRole]:
    role_ids = {
        resolve_user_role_id_for_team(event.actor, event.team_id)
        for event in events
        if event.actor is not None
    }
    role_ids.discard(None)
    if not role_ids:
        return {}

    roles = (
        db.session.query(UserRole)
        .options(selectinload(UserRole.base_role))
        .filter(UserRole.id.in_(role_ids))
        .all()
    )
    return {role.id: role for role in roles}


def _load_changes_by_event_id(
    order_id: int,
    events: list,
    ctx: ServiceContext,
) -> dict[str, list[dict]]:
    event_ids = [event.event_id for event in events if event.event_id]
    if not event_ids:
        return {}

    audit_query = db.session.query(OrderAuditLog).filter(
        OrderAuditLog.order_id == order_id,
        OrderAuditLog.event_id.in_(event_ids),
    )
    if ctx.team_id:
        audit_query = audit_query.filter(OrderAuditLog.team_id == ctx.team_id)
    rows = audit_query.order_by(OrderAuditLog.id.asc()).all()

    item_state_names_by_id = _load_item_state_names(rows)
    changes_by_event_id: dict[str, list[dict]] = {}
    for row in rows:
        changes_by_event_id.setdefault(row.event_id, []).append(
            serialize_order_audit_change(row, item_state_names_by_id)
        )
    return changes_by_event_id


def _load_item_state_names(rows: list) -> dict[int, str]:
    state_ids = {
        value
        for row in rows
        if row.field_name == ITEM_STATE_FIELD
        for value in (row.from_value, row.to_value)
        if isinstance(value, int)
    }
    if not state_ids:
        return {}

    states = db.session.query(ItemState).filter(ItemState.id.in_(state_ids)).all()
    return {state.id: state.name for state in states}


def _relayed_by_user_id(event) -> int | None:
    value = (event.payload or {}).get("relayed_by_user_id")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _load_relay_users(events: list) -> dict[int, User]:
    user_ids = {_relayed_by_user_id(event) for event in events}
    user_ids.discard(None)
    if not user_ids:
        return {}

    users = db.session.query(User).filter(User.id.in_(user_ids)).all()
    return {user.id: user for user in users}


def _serialize_relayed_by(event, relay_users_by_id: dict[int, User]) -> dict | None:
    user = relay_users_by_id.get(_relayed_by_user_id(event))
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def _serialize_event(
    event,
    roles_by_id: dict[int, UserRole],
    changes_by_event_id: dict[str, list[dict]],
    relay_users_by_id: dict[int, User],
) -> dict:
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
        "actor": _serialize_actor(event, roles_by_id),
        "origin": resolve_order_event_origin(
            event.event_name, event.payload, event.actor_id
        ),
        "relayed_by": _serialize_relayed_by(event, relay_users_by_id),
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
        "changes": changes_by_event_id.get(event.event_id, []),
    }


def get_order_event_history(order_id: int, ctx: ServiceContext) -> dict:
    order_query = db.session.query(Order)
    if ctx.team_id:
        order_query = order_query.filter(Order.team_id == ctx.team_id)
    order = order_query.filter(Order.id == order_id).first()

    if order is None:
        raise NotFound(f"Order with id: {order_id} does not exist.")

    event_query = db.session.query(OrderEvent).options(
        selectinload(OrderEvent.actions),
        selectinload(OrderEvent.actor),
    )
    if ctx.team_id:
        event_query = event_query.filter(OrderEvent.team_id == ctx.team_id)

    events = (
        event_query
        .filter(OrderEvent.order_id == order_id)
        .order_by(OrderEvent.occurred_at.desc(), OrderEvent.id.desc())
        .all()
    )

    roles_by_id = _load_actor_roles(events)
    changes_by_event_id = _load_changes_by_event_id(order_id, events, ctx)
    relay_users_by_id = _load_relay_users(events)

    return {
        "order_id": order_id,
        "order_events": [
            _serialize_event(event, roles_by_id, changes_by_event_id, relay_users_by_id)
            for event in events
        ],
    }
