from flask import request
from flask_socketio import disconnect, join_room

from Delivery_app_BK.sockets.connection.auth import verify_socket_claims
from Delivery_app_BK.sockets.notifications import emit_notification_snapshot_for_claims
from Delivery_app_BK.sockets.connection.state import active_user_sessions
from Delivery_app_BK.sockets.rooms.names import build_user_app_room, build_user_room
from Delivery_app_BK.socketio_instance import socketio


def handle_connect(*_args, **_kwargs):
    claims = verify_socket_claims()
    if not claims:
        return False

    user_id = claims.get("user_id")
    app_scope = claims.get("app_scope")
    if user_id is None:
        disconnect()
        return False

    join_room(build_user_room(user_id), sid=request.sid)
    if isinstance(app_scope, str):
        join_room(build_user_app_room(user_id, app_scope), sid=request.sid)
    active_user_sessions.setdefault(int(user_id), set()).add(request.sid)
    emit_notification_snapshot_for_claims(claims)
    return True


def handle_disconnect():
    sid = request.sid
    for user_id, sessions in list(active_user_sessions.items()):
        if sid in sessions:
            sessions.remove(sid)
            if not sessions:
                active_user_sessions.pop(user_id, None)
            break
