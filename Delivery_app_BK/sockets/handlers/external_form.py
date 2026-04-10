from flask import request
from flask_socketio import join_room, leave_room

from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.connection.auth import authenticated_socket_event
from Delivery_app_BK.sockets.contracts.realtime import (
    SERVER_EVENT_EXTERNAL_FORM_RECEIVED,
    SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
)
from Delivery_app_BK.sockets.rooms.names import build_external_form_room


@authenticated_socket_event
def handle_external_form_join_user(claims, data):
    team_id = claims.get("active_team_id") or claims.get("team_id")
    target_user_id = (data or {}).get("user_id")
    if team_id is None or target_user_id is None:
        return

    join_room(build_external_form_room(team_id, target_user_id), sid=request.sid)


@authenticated_socket_event
def handle_external_form_leave_user(claims, data):
    team_id = claims.get("active_team_id") or claims.get("team_id")
    target_user_id = (data or {}).get("user_id")
    if team_id is None or target_user_id is None:
        return

    leave_room(build_external_form_room(team_id, target_user_id), sid=request.sid)


@authenticated_socket_event
def handle_external_form_submit_user(claims, data):
    team_id = claims.get("active_team_id") or claims.get("team_id")
    target_user_id = (data or {}).get("user_id")
    form_data = (data or {}).get("form_data")
    if team_id is None or target_user_id is None or not form_data:
        return

    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_RECEIVED,
        {
            "form_data": form_data,
            "submitted_by": claims.get("user_id"),
        },
        room=build_external_form_room(team_id, target_user_id),
        skip_sid=request.sid,
    )


@authenticated_socket_event
def handle_external_form_request_user(claims, data):
    team_id = claims.get("active_team_id") or claims.get("team_id")
    target_user_id = (data or {}).get("user_id")
    request_data = (data or {}).get("request_data")
    if team_id is None or target_user_id is None:
        return

    socketio.emit(
        SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
        {
            "request_data": request_data or {},
            "requested_by": claims.get("user_id"),
        },
        room=build_external_form_room(team_id, target_user_id),
        skip_sid=request.sid,
    )
