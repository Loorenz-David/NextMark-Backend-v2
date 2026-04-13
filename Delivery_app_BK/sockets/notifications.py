from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1

from flask import request
from flask import current_app
from sqlalchemy import func

from Delivery_app_BK.models import (
    BaseRole,
    RouteGroup,
    Order,
    RouteSolution,
    RouteSolutionStop,
    User,
    UserRole,
    db,
)
from Delivery_app_BK.services.domain.user import ADMIN_APP_SCOPE, DRIVER_APP_SCOPE
from Delivery_app_BK.services.infra.web_push.sender import send_web_push_to_users
from Delivery_app_BK.services.domain.order.order_states import OrderState as OrderStateDomain, OrderStateId
from Delivery_app_BK.services.infra.redis import (
    add_unread_notification,
    get_unread_count,
    list_unread_notifications,
    mark_notifications_read,
)
from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.connection.auth import authenticated_socket_event, emit_socket_error
from Delivery_app_BK.sockets.contracts.realtime import (
    CLIENT_EVENT_NOTIFICATION_MARK_READ,
    SERVER_EVENT_NOTIFICATION_EVENT,
    SERVER_EVENT_NOTIFICATION_SNAPSHOT,
)
from Delivery_app_BK.sockets.rooms.names import build_user_app_room

ADMIN_NOTIFICATION_BASE_ROLES = {"admin", "assistant"}
DELIVERY_PLANNING_NOTIFICATION_EVENT_NAMES = {
    "route_plan.created",
    "route_plan.updated",
    "route_plan.deleted",
    "route_group.updated",
    "route_solution.created",
    "route_solution.updated",
    "route_solution.deleted",
    "route_solution_stop.updated",
}
SUPPRESSED_DUPLICATE_ORDER_NOTIFICATION_EVENT_NAMES = {
    "order_preparing",
    "order_ready",
    "order_processing",
    "order_completed",
    "order_failed",
    "order_cancelled",
}

ORDER_STATE_NAME_BY_ID = {
    OrderStateId.DRAFT: OrderStateDomain.DRAFT.value,
    OrderStateId.CONFIRMED: OrderStateDomain.CONFIRMED.value,
    OrderStateId.PREPARING: OrderStateDomain.PREPARING.value,
    OrderStateId.READY: OrderStateDomain.READY.value,
    OrderStateId.PROCESSING: OrderStateDomain.PROCESSING.value,
    OrderStateId.COMPLETED: OrderStateDomain.COMPLETED.value,
    OrderStateId.FAIL: OrderStateDomain.FAIL.value,
    OrderStateId.CANCELLED: OrderStateDomain.CANCELLED.value,
}
ORDER_STATE_NAME_BY_ORIGINAL_EVENT = {
    "order_created": OrderStateDomain.DRAFT.value,
    "order_confirmed": OrderStateDomain.CONFIRMED.value,
    "order_preparing": OrderStateDomain.PREPARING.value,
    "order_ready": OrderStateDomain.READY.value,
    "order_processing": OrderStateDomain.PROCESSING.value,
    "order_completed": OrderStateDomain.COMPLETED.value,
    "order_failed": OrderStateDomain.FAIL.value,
    "order_cancelled": OrderStateDomain.CANCELLED.value,
}


def emit_notification_snapshot_for_claims(claims: dict) -> None:
    user_id = claims.get("user_id")
    app_scope = claims.get("app_scope")
    if not isinstance(user_id, int) or not isinstance(app_scope, str):
        return

    notifications = list_unread_notifications(user_id=user_id, app_scope=app_scope)
    socketio.emit(
        SERVER_EVENT_NOTIFICATION_SNAPSHOT,
        {
            "notifications": notifications,
            "unread_count": get_unread_count(user_id=user_id, app_scope=app_scope),
        },
        room=request.sid,
    )


@authenticated_socket_event
def handle_notification_mark_read(claims: dict, data: dict | None) -> None:
    user_id = claims.get("user_id")
    app_scope = claims.get("app_scope")
    if not isinstance(user_id, int) or not isinstance(app_scope, str):
        emit_socket_error(code="invalid_claims", error="Notification read requires a valid socket session.")
        return

    notification_ids = data.get("notification_ids") if isinstance(data, dict) else None
    if not isinstance(notification_ids, list):
        emit_socket_error(code="invalid_notification_ids", error="notification_ids must be a list.")
        return

    mark_notifications_read(
        user_id=user_id,
        app_scope=app_scope,
        notification_ids=[str(notification_id) for notification_id in notification_ids],
    )
    socketio.emit(
        SERVER_EVENT_NOTIFICATION_SNAPSHOT,
        {
            "notifications": list_unread_notifications(user_id=user_id, app_scope=app_scope),
            "unread_count": get_unread_count(user_id=user_id, app_scope=app_scope),
        },
        room=build_user_app_room(user_id, app_scope),
    )


def notify_order_event(
    *,
    event_id: str,
    event_name: str,
    driver_event_name: str | None = None,
    team_id: int | None,
    order_id: int | None,
    payload: dict | None,
    occurred_at,
    actor: User | None,
) -> None:
    if team_id is None or order_id is None:
        return

    payload = payload or {}
    if _should_suppress_order_notification(payload):
        return

    order = db.session.get(Order, order_id)
    if order is None:
        return

    admin_recipients = resolve_admin_notification_recipients(team_id=team_id, actor_user_id=actor.id if actor else None)
    driver_recipients = resolve_driver_notification_recipients(
        team_id=team_id,
        order_id=order_id,
        actor_user_id=actor.id if actor else None,
    )
    occurred_iso = _to_iso_string(occurred_at)

    for recipient in admin_recipients:
        target = _build_notification_target(
            app_scope=recipient["app_scope"],
            event_name=event_name,
            order=order,
            payload=payload,
            route_id=recipient.get("route_id"),
            entity_type="order",
            entity_id=order_id,
        )
        if target is None:
            continue

        notification = build_notification_item(
            event_id=event_id,
            recipient_user_id=recipient["user_id"],
            app_scope=recipient["app_scope"],
            kind=event_name,
            entity_type="order",
            entity_id=order_id,
            team_id=team_id,
            actor=actor,
            title=_build_notification_title(event_name),
            description=_build_notification_description(
                event_name=event_name,
                order=order,
                payload=payload,
            ),
            occurred_at=occurred_iso,
            target=target,
            related_ids=_build_related_ids(payload=payload, order_id=order_id),
        )
        _store_and_emit_notification(recipient["user_id"], recipient["app_scope"], notification)


def build_realtime_notification_preview(
    *,
    event_name: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict | None,
) -> dict:
    resolved_payload = payload if isinstance(payload, dict) else {}
    order = _resolve_preview_order(
        event_name=event_name,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=resolved_payload,
    )
    return {
        "kind": event_name,
        "title": _build_notification_title(event_name),
        "description": _build_notification_description(
            event_name=event_name,
            order=order,
            payload=resolved_payload,
        ),
    }

    effective_driver_event_name = driver_event_name or event_name

    for recipient in driver_recipients:
        target = _build_notification_target(
            app_scope=recipient["app_scope"],
            event_name=effective_driver_event_name,
            order=order,
            payload=payload,
            route_id=recipient.get("route_id"),
            entity_type="order",
            entity_id=order_id,
        )
        if target is None:
            continue

        notification = build_notification_item(
            event_id=event_id,
            recipient_user_id=recipient["user_id"],
            app_scope=recipient["app_scope"],
            kind=effective_driver_event_name,
            entity_type="order",
            entity_id=order_id,
            team_id=team_id,
            actor=actor,
            title=_build_notification_title(effective_driver_event_name),
            description=_build_notification_description(
                event_name=effective_driver_event_name,
                order=order,
                payload=payload,
            ),
            occurred_at=occurred_iso,
            target=target,
            related_ids=_build_related_ids(payload=payload, order_id=order_id),
        )
        _store_and_emit_notification(recipient["user_id"], recipient["app_scope"], notification)


def notify_app_event(
    *,
    event_id: str,
    event_name: str,
    team_id: int | None,
    entity_type: str,
    entity_id: int | None,
    payload: dict | None,
    occurred_at,
    actor: User | None,
) -> None:
    if team_id is None:
        return

    payload = payload or {}
    order_id = _parse_int(payload.get("order_id"))
    order = db.session.get(Order, order_id) if order_id is not None else None
    if event_name == "order_chat.message_created" and order is None:
        return

    recipients = [
        *(resolve_admin_notification_recipients(team_id=team_id, actor_user_id=actor.id if actor else None)),
        *(
            resolve_driver_notification_recipients(
                team_id=team_id,
                order_id=order_id,
                actor_user_id=actor.id if actor else None,
            )
        ),
    ]
    occurred_iso = _to_iso_string(occurred_at)

    for recipient in recipients:
        target = _build_notification_target(
            app_scope=recipient["app_scope"],
            event_name=event_name,
            order=order,
            payload=payload,
            route_id=recipient.get("route_id"),
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if target is None:
            continue

        notification = build_notification_item(
            event_id=event_id,
            recipient_user_id=recipient["user_id"],
            app_scope=recipient["app_scope"],
            kind=event_name,
            entity_type=entity_type,
            entity_id=entity_id,
            team_id=team_id,
            actor=actor,
            title=_build_notification_title(event_name),
            description=_build_notification_description(
                event_name=event_name,
                order=order,
                payload=payload,
            ),
            occurred_at=occurred_iso,
            target=target,
            related_ids=_build_related_ids(payload=payload, order_id=order_id),
        )
        _store_and_emit_notification(recipient["user_id"], recipient["app_scope"], notification)


def notify_delivery_planning_event(
    *,
    event_id: str,
    event_name: str,
    team_id: int | None,
    entity_type: str,
    entity_id: int | None,
    payload: dict | None,
    occurred_at,
    actor: User | None,
) -> None:
    if team_id is None or event_name not in DELIVERY_PLANNING_NOTIFICATION_EVENT_NAMES:
        return

    payload = payload or {}
    route_id = _parse_int(payload.get("route_solution_id"))
    route_group_id = _resolve_route_group_id(payload)
    driver_id = _parse_int(payload.get("driver_id")) or _parse_int(payload.get("old_driver_id"))

    recipients = [
        *(resolve_admin_notification_recipients(team_id=team_id, actor_user_id=actor.id if actor else None)),
        *(
            resolve_driver_notification_recipients(
                team_id=team_id,
                route_id=route_id,
                route_group_id=route_group_id,
                driver_id=driver_id,
                actor_user_id=actor.id if actor else None,
            )
        ),
    ]
    current_app.logger.info(
        "notify_delivery_planning_event resolved recipients | event=%s team_id=%s route_id=%s route_group_id=%s driver_id=%s recipients=%s",
        event_name,
        team_id,
        route_id,
        route_group_id,
        driver_id,
        recipients,
    )
    occurred_iso = _to_iso_string(occurred_at)

    for recipient in recipients:
        target = _build_notification_target(
            app_scope=recipient["app_scope"],
            event_name=event_name,
            order=None,
            payload=payload,
            route_id=recipient.get("route_id"),
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if target is None:
            continue

        notification = build_notification_item(
            event_id=event_id,
            recipient_user_id=recipient["user_id"],
            app_scope=recipient["app_scope"],
            kind=event_name,
            entity_type=entity_type,
            entity_id=entity_id,
            team_id=team_id,
            actor=actor,
            title=_build_notification_title(event_name),
            description=_build_notification_description(
                event_name=event_name,
                order=None,
                payload=payload,
            ),
            occurred_at=occurred_iso,
            target=target,
            related_ids=_build_related_ids(payload=payload),
        )
        _store_and_emit_notification(recipient["user_id"], recipient["app_scope"], notification)


def resolve_admin_notification_recipients(*, team_id: int, actor_user_id: int | None) -> list[dict]:
    rows = (
        db.session.query(User.id)
        .join(UserRole, User.user_role_id == UserRole.id)
        .join(BaseRole, UserRole.base_role_id == BaseRole.id)
        .filter(
            User.team_id == team_id,
            func.lower(BaseRole.role_name).in_(tuple(ADMIN_NOTIFICATION_BASE_ROLES)),
        )
        .distinct()
        .all()
    )
    return [
        {"user_id": int(user_id), "app_scope": ADMIN_APP_SCOPE}
        for (user_id,) in rows
        if isinstance(user_id, int) and user_id != actor_user_id
    ]


def resolve_driver_notification_recipients(
    *,
    team_id: int,
    order_id: int | None = None,
    route_id: int | None = None,
    route_group_id: int | None = None,
    driver_id: int | None = None,
    actor_user_id: int | None,
) -> list[dict]:
    rows: list[tuple[int, int]] = []

    if route_id is not None:
        rows = (
            db.session.query(RouteSolution.driver_id, RouteSolution.id)
            .filter(
                RouteSolution.team_id == team_id,
                RouteSolution.id == route_id,
                RouteSolution.is_selected.is_(True),
                RouteSolution.driver_id.isnot(None),
            )
            .distinct()
            .all()
        )
    elif route_group_id is not None:
        rows = (
            db.session.query(RouteSolution.driver_id, RouteSolution.id)
            .filter(
                RouteSolution.team_id == team_id,
                RouteSolution.route_group_id == route_group_id,
                RouteSolution.is_selected.is_(True),
                RouteSolution.driver_id.isnot(None),
            )
            .distinct()
            .all()
        )
    elif order_id is not None:
        rows = (
            db.session.query(RouteSolution.driver_id, RouteSolution.id)
            .join(RouteSolutionStop, RouteSolutionStop.route_solution_id == RouteSolution.id)
            .filter(
                RouteSolution.team_id == team_id,
                RouteSolutionStop.team_id == team_id,
                RouteSolutionStop.order_id == order_id,
                RouteSolution.is_selected.is_(True),
                RouteSolution.driver_id.isnot(None),
            )
            .distinct()
            .all()
        )

    recipients = _dedupe_driver_recipients(rows, actor_user_id)
    if recipients:
        current_app.logger.info(
            "resolve_driver_notification_recipients matched rows | team_id=%s order_id=%s route_id=%s route_group_id=%s driver_id=%s recipients=%s",
            team_id,
            order_id,
            route_id,
            route_group_id,
            driver_id,
            recipients,
        )
        return recipients

    if (
        route_id is not None
        and isinstance(driver_id, int)
        and driver_id != actor_user_id
    ):
        fallback_recipients = [{
            "user_id": driver_id,
            "app_scope": DRIVER_APP_SCOPE,
            "route_id": route_id,
        }]
        current_app.logger.info(
            "resolve_driver_notification_recipients used fallback | team_id=%s route_id=%s driver_id=%s recipients=%s",
            team_id,
            route_id,
            driver_id,
            fallback_recipients,
        )
        return fallback_recipients

    current_app.logger.info(
        "resolve_driver_notification_recipients found no recipients | team_id=%s order_id=%s route_id=%s route_group_id=%s driver_id=%s actor_user_id=%s",
        team_id,
        order_id,
        route_id,
        route_group_id,
        driver_id,
        actor_user_id,
    )
    return []


def _dedupe_driver_recipients(rows: list[tuple[int, int]], actor_user_id: int | None) -> list[dict]:
    recipients: list[dict] = []
    seen: set[tuple[int, int]] = set()

    for driver_id, route_id in rows:
        if not isinstance(driver_id, int) or driver_id == actor_user_id:
            continue
        if not isinstance(route_id, int):
            continue

        key = (driver_id, route_id)
        if key in seen:
            continue
        seen.add(key)
        recipients.append({
            "user_id": driver_id,
            "app_scope": DRIVER_APP_SCOPE,
            "route_id": route_id,
        })

    return recipients


def build_notification_item(
    *,
    event_id: str,
    recipient_user_id: int,
    app_scope: str,
    kind: str,
    entity_type: str,
    entity_id: int | None,
    team_id: int | None,
    actor: User | None,
    title: str,
    description: str,
    occurred_at: str,
    target: dict,
    related_ids: dict | None = None,
) -> dict:
    notification_id = _build_notification_id(event_id=event_id, recipient_user_id=recipient_user_id, app_scope=app_scope)
    payload = {
        "notification_id": notification_id,
        "event_id": event_id,
        "kind": kind,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "team_id": team_id,
        "actor_user_id": actor.id if actor and isinstance(actor.id, int) else None,
        "actor_username": _resolve_actor_username(actor),
        "title": title,
        "description": description,
        "occurred_at": occurred_at,
        "target": target,
        "read": False,
    }
    if related_ids:
        payload.update({key: value for key, value in related_ids.items() if value is not None})
    return payload


def _store_and_emit_notification(user_id: int, app_scope: str, notification: dict) -> None:
    add_unread_notification(user_id=user_id, app_scope=app_scope, notification=notification)
    socketio.emit(
        SERVER_EVENT_NOTIFICATION_EVENT,
        notification,
        room=build_user_app_room(user_id, app_scope),
    )
    socketio.emit(
        SERVER_EVENT_NOTIFICATION_SNAPSHOT,
        {
            "notifications": list_unread_notifications(user_id=user_id, app_scope=app_scope),
            "unread_count": get_unread_count(user_id=user_id, app_scope=app_scope),
        },
        room=build_user_app_room(user_id, app_scope),
    )
    if app_scope == ADMIN_APP_SCOPE:
        target = notification.get("target")
        if isinstance(target, dict):
            try:
                send_web_push_to_users(
                    user_ids=[user_id],
                    title=notification.get("title", "New update"),
                    description=notification.get("description", ""),
                    notification_id=notification.get("notification_id", ""),
                    occurred_at=notification.get("occurred_at", ""),
                    target=target,
                )
            except Exception:
                current_app.logger.exception(
                    "web push delivery failed | notification_id=%s user_id=%s",
                    notification.get("notification_id"),
                    user_id,
                )


def _build_notification_id(*, event_id: str, recipient_user_id: int, app_scope: str) -> str:
    return sha1(f"{event_id}:{recipient_user_id}:{app_scope}".encode("utf-8")).hexdigest()


def _build_notification_title(event_name: str) -> str:
    mapping = {
        "order.created": "Order created",
        "order.updated": "Order updated",
        "order.state_changed": "Order state changed",
        "order_case.created": "New order case",
        "order_case.updated": "Order case updated",
        "order_case.state_changed": "Order case state changed",
        "order_chat.message_created": "New case message",
        "route_plan.created": "Route plan created",
        "route_plan.updated": "Route plan updated",
        "route_plan.deleted": "Route plan deleted",
        "route_group.updated": "Route group updated",
        "route_solution.created": "Route created",
        "route_solution.updated": "Route updated",
        "route_solution.deleted": "Route deleted",
        "route_solution_stop.updated": "Route stop updated",
    }
    return mapping.get(event_name, "New update")


def _build_notification_description(*, event_name: str, order: Order | None, payload: dict) -> str:
    order_label = _build_order_label(order)
    plan_label = _resolve_plan_label(payload)
    route_label = _resolve_route_label(payload)
    route_subject = _resolve_route_subject_label(payload)

    if event_name == "order.created":
        return f"{order_label} was created."
    if event_name == "order.updated":
        return _build_order_updated_description(order_label=order_label, payload=payload)
    if event_name == "order.state_changed":
        old_state_name = _resolve_old_order_state_name(payload=payload)
        new_state_name = _resolve_new_order_state_name(payload=payload, order=order)
        if old_state_name and new_state_name and old_state_name != new_state_name:
            return f"{order_label} moved from {old_state_name} to {new_state_name}."
        if new_state_name:
            return f"{order_label} moved to {new_state_name}."
        return f"{order_label} changed state."
    if event_name == "order_case.created":
        return f"A new case was created for {order_label}."
    if event_name == "order_case.updated":
        return f"A case for {order_label} was updated."
    if event_name == "order_case.state_changed":
        state = payload.get("state")
        if isinstance(state, str) and state.strip():
            return f"A case for {order_label} changed to {state.strip()}."
        return f"A case for {order_label} changed state."
    if event_name == "order_chat.message_created":
        message = str(payload.get("message") or "").strip()
        if message:
            return message[:140]
        return f"There is a new message for {order_label}."
    if event_name == "route_plan.created":
        return f"{plan_label} was created."
    if event_name == "route_plan.updated":
        return f"{plan_label} was updated."
    if event_name == "route_plan.deleted":
        return f"{plan_label} was deleted."
    if event_name == "route_group.updated":
        return f"{plan_label} was updated."
    if event_name == "route_solution.created":
        return f"{route_subject} was created."
    if event_name == "route_solution.updated":
        return f"{route_subject} was updated."
    if event_name == "route_solution.deleted":
        return f"{route_subject} was deleted."
    if event_name == "route_solution_stop.updated":
        stop_order = _parse_int(payload.get("stop_order"))
        stop_label = f"Stop {stop_order}" if stop_order is not None else "A stop"
        client_label = payload.get("notification_client_label")
        arrival_label = payload.get("notification_arrival_label")
        if client_label and arrival_label:
            return f"{stop_label} on {route_label} — {client_label}, arriving {arrival_label}."
        if client_label:
            return f"{stop_label} on {route_label} — {client_label} was updated."
        if arrival_label:
            return f"{stop_label} on {route_label} — arriving {arrival_label}."
        return f"{stop_label} on {route_label} was updated."
    return "A new update is available."


def _build_order_updated_description(*, order_label: str, payload: dict) -> str:
    changed_sections = payload.get("changed_sections")
    if not isinstance(changed_sections, list):
        return f"{order_label} was updated."

    allowed_sections = [
        section
        for section in changed_sections
        if section in {"details", "schedule", "items"}
    ]
    if not allowed_sections:
        return f"{order_label} was updated."

    labels_by_section = {
        "details": "details",
        "schedule": "schedule",
        "items": "items",
    }
    labels = [labels_by_section[section] for section in dict.fromkeys(allowed_sections)]

    if len(labels) == 1:
        return f"{order_label} {labels[0]} were updated."

    if len(labels) == 2:
        return f"{order_label} {labels[0]} and {labels[1]} were updated."

    joined_labels = ", ".join(labels[:-1])
    return f"{order_label} {joined_labels}, and {labels[-1]} were updated."


def _build_order_label(order: Order | None) -> str:
    scalar_id = getattr(order, "order_scalar_id", None) if order is not None else None

    if isinstance(scalar_id, int):
        return f"Order #{scalar_id}"

    reference = order.reference_number if order and order.reference_number else None
    if reference:
        return f"Order #{reference}"

    if order and isinstance(order.id, int):
        return f"Order #{order.id}"

    return "Order"


def _resolve_preview_order(
    *,
    event_name: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict,
) -> Order | None:
    order_id = _parse_int(payload.get("order_id"))
    if order_id is None and entity_type == "order" and isinstance(entity_id, int):
        order_id = entity_id
    if order_id is None and event_name.startswith("order.") and isinstance(entity_id, int):
        order_id = entity_id
    if order_id is None:
        return None
    return db.session.get(Order, order_id)


def _should_suppress_order_notification(payload: dict) -> bool:
    original_event_name = payload.get("original_event_name")
    if not isinstance(original_event_name, str):
        return False

    if original_event_name in SUPPRESSED_DUPLICATE_ORDER_NOTIFICATION_EVENT_NAMES:
        return True

    if original_event_name == "order_confirmed" and "order_plan_objective" not in payload:
        return True

    return False


def _build_notification_target(
    *,
    app_scope: str,
    event_name: str,
    order: Order | None,
    payload: dict,
    route_id: int | None,
    entity_type: str | None,
    entity_id: int | None,
) -> dict | None:
    order_id = order.id if order and isinstance(order.id, int) else _parse_int(payload.get("order_id"))
    order_case_id = _parse_int(payload.get("order_case_id"))
    order_case_client_id = payload.get("order_case_client_id") if isinstance(payload.get("order_case_client_id"), str) else None
    plan_id = _resolve_plan_id(event_name=event_name, payload=payload, entity_type=entity_type, entity_id=entity_id)
    route_group_id = _resolve_route_group_id(payload)
    route_solution_id = _parse_int(payload.get("route_solution_id"))
    route_solution_stop_id = _parse_int(payload.get("route_solution_stop_id"))

    if app_scope == DRIVER_APP_SCOPE:
        if route_id is None:
            return None

        if (
            event_name == "order_chat.message_created"
            and order_id is not None
            and order_case_id is not None
            and isinstance(order_case_client_id, str)
            and order_case_client_id
        ):
            return {
                "kind": "driver_order_case_chat",
                "route": "/",
                "params": {
                    "routeId": route_id,
                    "orderId": order_id,
                    "orderCaseId": order_case_id,
                    "orderCaseClientId": order_case_client_id,
                },
            }

        params = {"routeId": route_id}
        if order_id is not None:
            params["orderId"] = order_id
        if order_case_id is not None:
            params["orderCaseId"] = order_case_id
        if isinstance(order_case_client_id, str) and order_case_client_id:
            params["orderCaseClientId"] = order_case_client_id
        if plan_id is not None:
            params["planId"] = plan_id
        if route_group_id is not None:
            params["routeGroupId"] = route_group_id
        if route_solution_id is not None:
            params["routeSolutionId"] = route_solution_id
        if route_solution_stop_id is not None:
            params["routeSolutionStopId"] = route_solution_stop_id
        return {
            "kind": "route_execution",
            "route": "/",
            "params": params,
        }

    if event_name in DELIVERY_PLANNING_NOTIFICATION_EVENT_NAMES:
        if plan_id is None:
            return None
        params = {"planId": plan_id}
        if route_group_id is not None:
            params["routeGroupId"] = route_group_id
        if route_solution_id is not None:
            params["routeSolutionId"] = route_solution_id
        if route_solution_stop_id is not None:
            params["routeSolutionStopId"] = route_solution_stop_id
        return {
            "kind": "local_delivery_workspace",
            "route": "/",
            "params": params,
        }

    if event_name in {"order.created", "order.updated", "order.state_changed"} and order_id is not None:
        return {
            "kind": "order_detail",
            "route": "/",
            "params": {"orderId": order_id},
        }

    if event_name in {"order_case.created", "order_case.updated", "order_case.state_changed"} and order_case_id is not None:
        return {
            "kind": "order_case_detail",
            "route": "/",
            "params": {
                "orderId": order_id,
                "orderCaseId": order_case_id,
                "orderCaseClientId": order_case_client_id,
            },
        }

    if event_name == "order_chat.message_created" and order_case_id is not None:
        return {
            "kind": "order_case_chat",
            "route": "/",
            "params": {
                "orderId": order_id,
                "orderCaseId": order_case_id,
                "orderCaseClientId": order_case_client_id,
            },
        }

    return None


def _resolve_old_order_state_name(*, payload: dict) -> str | None:
    explicit_name = payload.get("old_order_state_name")
    if isinstance(explicit_name, str) and explicit_name.strip():
        return explicit_name.strip()

    old_state_id = _parse_int(payload.get("old_order_state_id"))
    if old_state_id is not None:
        return ORDER_STATE_NAME_BY_ID.get(old_state_id)

    return None


def _resolve_new_order_state_name(*, payload: dict, order: Order | None) -> str | None:
    explicit_name = payload.get("new_order_state_name")
    if isinstance(explicit_name, str) and explicit_name.strip():
        return explicit_name.strip()

    state_name = payload.get("state_name")
    if isinstance(state_name, str) and state_name.strip():
        return state_name.strip()

    new_state_id = _parse_int(payload.get("new_order_state_id"))
    if new_state_id is not None:
        resolved = ORDER_STATE_NAME_BY_ID.get(new_state_id)
        if resolved:
            return resolved

    state_id = _parse_int(payload.get("order_state_id"))
    if state_id is not None:
        resolved = ORDER_STATE_NAME_BY_ID.get(state_id)
        if resolved:
            return resolved

    original_event_name = payload.get("original_event_name")
    if isinstance(original_event_name, str):
        resolved = ORDER_STATE_NAME_BY_ORIGINAL_EVENT.get(original_event_name.strip())
        if resolved:
            return resolved

    state = getattr(order, "state", None)
    state_model_name = getattr(state, "name", None)
    if isinstance(state_model_name, str) and state_model_name.strip():
        return state_model_name.strip()

    return None


def _build_related_ids(*, payload: dict, order_id: int | None = None) -> dict:
    route_plan_id = _parse_int(payload.get("route_plan_id"))

    route_group_id = _resolve_route_group_id(payload)

    related_ids = {
        "order_id": order_id if order_id is not None else _parse_int(payload.get("order_id")),
        "order_case_id": _parse_int(payload.get("order_case_id")),
        "order_case_client_id": payload.get("order_case_client_id") if isinstance(payload.get("order_case_client_id"), str) else None,
        "plan_id": route_plan_id,
        "route_group_id": route_group_id,
        "route_solution_id": _parse_int(payload.get("route_solution_id")),
        "route_solution_stop_id": _parse_int(payload.get("route_solution_stop_id")),
        "route_freshness_updated_at": payload.get("route_freshness_updated_at") if isinstance(payload.get("route_freshness_updated_at"), str) else None,
    }
    return {key: value for key, value in related_ids.items() if value is not None}


def _resolve_plan_id(*, event_name: str, payload: dict, entity_type: str | None, entity_id: int | None) -> int | None:
    plan_id = _parse_int(payload.get("route_plan_id"))
    if plan_id is not None:
        return plan_id

    if event_name.startswith("route_plan.") and entity_type == "route_plan" and isinstance(entity_id, int):
        return entity_id

    route_group_id = _resolve_route_group_id(payload)
    if route_group_id is not None:
        route_group = db.session.get(RouteGroup, route_group_id)
        route_plan_id = _get_route_group_route_plan_id(route_group)
        if isinstance(route_plan_id, int):
            return route_plan_id

    route_solution_id = _parse_int(payload.get("route_solution_id"))
    if route_solution_id is not None:
        route_solution = db.session.get(RouteSolution, route_solution_id)
        route_group_id = _get_route_solution_route_group_id(route_solution)
        if isinstance(route_group_id, int):
            route_group = db.session.get(RouteGroup, route_group_id)
            route_plan_id = _get_route_group_route_plan_id(route_group)
            if isinstance(route_plan_id, int):
                return route_plan_id

    route_solution_stop_id = _parse_int(payload.get("route_solution_stop_id"))
    if route_solution_stop_id is not None:
        stop = db.session.get(RouteSolutionStop, route_solution_stop_id)
        if stop is not None and isinstance(stop.route_solution_id, int):
            route_solution = db.session.get(RouteSolution, stop.route_solution_id)
            route_group_id = _get_route_solution_route_group_id(route_solution)
            if isinstance(route_group_id, int):
                route_group = db.session.get(RouteGroup, route_group_id)
                route_plan_id = _get_route_group_route_plan_id(route_group)
                if isinstance(route_plan_id, int):
                    return route_plan_id

    return None


def _resolve_route_group_id(payload: dict) -> int | None:
    return _parse_int(payload.get("route_group_id"))


def _get_route_group_route_plan_id(route_group: RouteGroup | None) -> int | None:
    if route_group is None:
        return None
    return getattr(route_group, "route_plan_id", None)


def _get_route_solution_route_group_id(route_solution: RouteSolution | None) -> int | None:
    if route_solution is None:
        return None
    return getattr(route_solution, "route_group_id", None)


def _resolve_plan_label(payload: dict) -> str:
    label = payload.get("label")
    plan_type = payload.get("plan_type")

    if isinstance(label, str) and label.strip():
        if plan_type == "route_plan":
            prefix = "Route plan"
        elif plan_type == "local_delivery":
            prefix = "Local delivery plan"
        else:
            prefix = "Delivery plan"
        return f'{prefix} "{label.strip()}"'

    if plan_type == "route_plan":
        return "Route plan"
    if plan_type == "local_delivery":
        return "Local delivery plan"

    return "Delivery plan"


def _resolve_route_label(payload: dict) -> str:
    label = payload.get("label")
    if isinstance(label, str) and label.strip():
        return f'Route "{label.strip()}"'
    return "Route"


def _resolve_route_subject_label(payload: dict) -> str:
    plan_label = payload.get("plan_label")
    if isinstance(plan_label, str) and plan_label.strip():
        plan_type = payload.get("plan_type")
        if plan_type == "route_plan":
            prefix = "Route plan"
        elif plan_type == "local_delivery":
            prefix = "Local delivery plan"
        else:
            prefix = "Delivery plan"
        return f'{prefix} "{plan_label.strip()}"'

    return _resolve_route_label(payload)


def _parse_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _resolve_actor_username(actor: User | None) -> str | None:
    if actor is None:
        return None
    username = getattr(actor, "username", None)
    if isinstance(username, str) and username.strip():
        return username.strip()
    email = getattr(actor, "email", None)
    if isinstance(email, str) and email.strip():
        return email.strip()
    return None


def _to_iso_string(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return datetime.now(timezone.utc).isoformat()
