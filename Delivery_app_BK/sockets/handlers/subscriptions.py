from flask import request
from flask_socketio import join_room, leave_room

from Delivery_app_BK.models import Order, RouteSolution, db
from Delivery_app_BK.services.domain.user import DRIVER_APP_SCOPE
from Delivery_app_BK.sockets.connection.auth import authenticated_socket_event, emit_socket_error
from Delivery_app_BK.sockets.contracts.realtime import (
    ALLOWED_APP_SCOPES_BY_CHANNEL,
    ALLOWED_CHANNELS,
    CHANNEL_ORDER_CHAT,
    CHANNEL_ROUTE_ORDERS,
    CHANNEL_TEAM_ADMIN,
    CHANNEL_TEAM_DRIVER_LIVE,
    CHANNEL_TEAM_MEMBERS,
    CHANNEL_TEAM_ORDERS,
    CHANNEL_TEAM_ORDER_CASES,
)
from Delivery_app_BK.sockets.rooms.names import (
    build_team_admin_room,
    build_order_chat_room,
    build_route_orders_room,
    build_team_members_room,
    build_team_order_cases_room,
    build_team_orders_room,
)
from Delivery_app_BK.sockets.telemetry.driver_live import (
    subscribe_team_driver_live,
    unsubscribe_team_driver_live,
)


def _require_allowed_channel(claims: dict, channel: str) -> bool:
    if channel not in ALLOWED_CHANNELS:
        emit_socket_error(code="unknown_channel", error="Realtime channel is not supported.")
        return False

    app_scope = claims.get("app_scope")
    if app_scope not in ALLOWED_APP_SCOPES_BY_CHANNEL.get(channel, set()):
        emit_socket_error(code="forbidden_channel", error="This session cannot access the requested realtime channel.")
        return False

    if claims.get("active_team_id") is None and channel != CHANNEL_ORDER_CHAT:
        emit_socket_error(code="missing_team", error="A team workspace is required for this realtime channel.")
        return False

    return True


def _resolve_order_chat_room(claims: dict, params: dict | None) -> str | None:
    order_id = (params or {}).get("order_id")
    if not isinstance(order_id, int):
        emit_socket_error(code="invalid_order_id", error="order_id is required for order chat subscriptions.")
        return None

    order = db.session.get(Order, order_id)
    team_id = claims.get("active_team_id") or claims.get("team_id")
    if not order or order.team_id != team_id:
        emit_socket_error(code="forbidden_order_chat", error="This session cannot access the requested order chat.")
        return None

    return build_order_chat_room(team_id, order_id)


def _resolve_route_orders_room(claims: dict, params: dict | None) -> str | None:
    route_id = (params or {}).get("route_id")
    if not isinstance(route_id, int):
        emit_socket_error(code="invalid_route_id", error="route_id is required for route order subscriptions.")
        return None

    team_id = claims.get("active_team_id") or claims.get("team_id")
    query = (
        db.session.query(RouteSolution)
        .filter(
            RouteSolution.id == route_id,
            RouteSolution.team_id == team_id,
            RouteSolution.is_selected.is_(True),
        )
    )

    if claims.get("app_scope") == DRIVER_APP_SCOPE:
        query = query.filter(RouteSolution.driver_id == claims.get("user_id"))

    route_solution = query.first()
    if route_solution is None:
        emit_socket_error(code="forbidden_route_orders", error="This session cannot access the requested route realtime channel.")
        return None

    return build_route_orders_room(team_id, route_id)


@authenticated_socket_event
def handle_subscribe(claims, data):
    channel = (data or {}).get("channel")
    params = (data or {}).get("params")
    if not isinstance(channel, str) or not _require_allowed_channel(claims, channel):
        return

    team_id = claims.get("active_team_id") or claims.get("team_id")

    if channel == CHANNEL_TEAM_ADMIN:
        join_room(build_team_admin_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_TEAM_ORDERS:
        join_room(build_team_orders_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_TEAM_ORDER_CASES:
        join_room(build_team_order_cases_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_ROUTE_ORDERS:
        room = _resolve_route_orders_room(claims, params if isinstance(params, dict) else None)
        if room:
            join_room(room, sid=request.sid)
        return

    if channel == CHANNEL_TEAM_DRIVER_LIVE:
        subscribe_team_driver_live(claims)
        return

    if channel == CHANNEL_TEAM_MEMBERS:
        join_room(build_team_members_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_ORDER_CHAT:
        room = _resolve_order_chat_room(claims, params if isinstance(params, dict) else None)
        if room:
            join_room(room, sid=request.sid)


@authenticated_socket_event
def handle_unsubscribe(claims, data):
    channel = (data or {}).get("channel")
    params = (data or {}).get("params")
    if not isinstance(channel, str) or channel not in ALLOWED_CHANNELS:
        return

    team_id = claims.get("active_team_id") or claims.get("team_id")

    if channel == CHANNEL_TEAM_ADMIN and team_id is not None:
        leave_room(build_team_admin_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_TEAM_ORDERS and team_id is not None:
        leave_room(build_team_orders_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_TEAM_ORDER_CASES and team_id is not None:
        leave_room(build_team_order_cases_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_ROUTE_ORDERS:
        room = _resolve_route_orders_room(claims, params if isinstance(params, dict) else None)
        if room:
            leave_room(room, sid=request.sid)
        return

    if channel == CHANNEL_TEAM_DRIVER_LIVE:
        unsubscribe_team_driver_live(claims)
        return

    if channel == CHANNEL_TEAM_MEMBERS and team_id is not None:
        leave_room(build_team_members_room(team_id), sid=request.sid)
        return

    if channel == CHANNEL_ORDER_CHAT:
        room = _resolve_order_chat_room(claims, params if isinstance(params, dict) else None)
        if room:
            leave_room(room, sid=request.sid)
