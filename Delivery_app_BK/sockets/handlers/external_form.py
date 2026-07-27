import logging

from flask import request
from flask_socketio import join_room, leave_room

from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.connection.auth import authenticated_socket_event
from Delivery_app_BK.sockets.contracts.realtime import (
    SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
    SERVER_EVENT_EXTERNAL_FORM_PROGRESS,
    SERVER_EVENT_EXTERNAL_FORM_RECEIVED,
    SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
)
from Delivery_app_BK.sockets.rooms.names import build_external_form_room

_EXTERNAL_FORM_ROOM_PREFIX = "external_form:"
logger = logging.getLogger(__name__)


def _team_id(claims):
    return claims.get("active_team_id") or claims.get("team_id")


def _room_member_count(room: str, *, exclude_sid: str | None = None) -> int:
    participants = socketio.server.manager.rooms.get("/", {}).get(room) or {}
    count = len(participants)
    if exclude_sid is not None and exclude_sid in participants:
        count -= 1
    return count


def _relay_ack(room: str) -> dict:
    return {
        "status": "relayed",
        "peers": _room_member_count(room, exclude_sid=request.sid),
    }


def _broadcast_presence(room: str, *, exclude_sid: str | None = None) -> None:
    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
        {"members": _room_member_count(room, exclude_sid=exclude_sid)},
        room=room,
    )


def broadcast_external_form_presence_on_disconnect(sid: str) -> None:
    # Runs from the disconnect handler, which python-socketio triggers before
    # removing the socket from its rooms — hence the explicit sid exclusion.
    for room in socketio.server.rooms(sid):
        if isinstance(room, str) and room.startswith(_EXTERNAL_FORM_ROOM_PREFIX):
            _broadcast_presence(room, exclude_sid=sid)


@authenticated_socket_event
def handle_external_form_join_user(claims, data):
    # Team-scoped room: any team device joins the same external-form channel,
    # so trusted-device user switching does not change room membership. The
    # payload user_id (if any) is ignored on purpose.
    team_id = _team_id(claims)
    if team_id is None:
        logger.warning(
            "[external-form-socket] join_rejected reason=missing_team sid=%s user_id=%s",
            request.sid,
            claims.get("user_id"),
        )
        return

    room = build_external_form_room(team_id)
    join_room(room, sid=request.sid)
    logger.info(
        "[external-form-socket] room_joined team_id=%s user_id=%s sid=%s members=%s",
        team_id,
        claims.get("user_id"),
        request.sid,
        _room_member_count(room),
    )
    _broadcast_presence(room)


@authenticated_socket_event
def handle_external_form_leave_user(claims, data):
    team_id = _team_id(claims)
    if team_id is None:
        logger.warning(
            "[external-form-socket] leave_rejected reason=missing_team sid=%s user_id=%s",
            request.sid,
            claims.get("user_id"),
        )
        return

    room = build_external_form_room(team_id)
    leave_room(room, sid=request.sid)
    logger.info(
        "[external-form-socket] room_left team_id=%s user_id=%s sid=%s members=%s",
        team_id,
        claims.get("user_id"),
        request.sid,
        _room_member_count(room),
    )
    _broadcast_presence(room)


@authenticated_socket_event
def handle_external_form_submit_user(claims, data):
    team_id = _team_id(claims)
    form_data = (data or {}).get("form_data")
    if team_id is None or not form_data:
        logger.warning(
            "[external-form-socket] submit_rejected reason=%s sid=%s user_id=%s",
            "missing_team" if team_id is None else "missing_form_data",
            request.sid,
            claims.get("user_id"),
        )
        return

    room = build_external_form_room(team_id)
    peers = _room_member_count(room, exclude_sid=request.sid)
    logger.info(
        "[external-form-socket] submit_relaying team_id=%s user_id=%s sid=%s peers=%s",
        team_id,
        claims.get("user_id"),
        request.sid,
        peers,
    )
    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_RECEIVED,
        {
            "form_data": form_data,
            "submitted_by": claims.get("user_id"),
        },
        room=room,
        skip_sid=request.sid,
    )
    return _relay_ack(room)


@authenticated_socket_event
def handle_external_form_progress_user(claims, data):
    # In-progress snapshot of the form being filled on the linked device.
    # Relayed opaquely like form_data: the frontend owns the progress_data
    # shape (form_data + step + seq + session).
    team_id = _team_id(claims)
    progress_data = (data or {}).get("progress_data")
    if team_id is None or not progress_data:
        logger.warning(
            "[external-form-socket] progress_rejected reason=%s sid=%s user_id=%s",
            "missing_team" if team_id is None else "missing_progress_data",
            request.sid,
            claims.get("user_id"),
        )
        return

    logger.debug(
        "[external-form-socket] progress_relaying team_id=%s user_id=%s sid=%s "
        "peers=%s session=%s seq=%s step=%s",
        team_id,
        claims.get("user_id"),
        request.sid,
        _room_member_count(
            build_external_form_room(team_id), exclude_sid=request.sid
        ),
        progress_data.get("session"),
        progress_data.get("seq"),
        progress_data.get("step"),
    )
    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_PROGRESS,
        {
            "progress_data": progress_data,
            "progressed_by": claims.get("user_id"),
        },
        room=build_external_form_room(team_id),
        skip_sid=request.sid,
    )


@authenticated_socket_event
def handle_external_form_request_user(claims, data):
    team_id = _team_id(claims)
    if team_id is None:
        logger.warning(
            "[external-form-socket] request_rejected reason=missing_team sid=%s user_id=%s",
            request.sid,
            claims.get("user_id"),
        )
        return

    room = build_external_form_room(team_id)
    request_data = (data or {}).get("request_data") or {}
    peers = _room_member_count(room, exclude_sid=request.sid)
    logger.info(
        "[external-form-socket] request_relaying team_id=%s user_id=%s sid=%s "
        "peers=%s trace_id=%s order_id=%s",
        team_id,
        claims.get("user_id"),
        request.sid,
        peers,
        request_data.get("diagnostic_trace_id"),
        request_data.get("order_id"),
    )
    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
        {
            "request_data": request_data,
            "requested_by": claims.get("user_id"),
        },
        room=room,
        skip_sid=request.sid,
    )
    return _relay_ack(room)
