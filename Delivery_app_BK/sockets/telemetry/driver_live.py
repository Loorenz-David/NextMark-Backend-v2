from datetime import datetime, timezone

from flask import request
from flask_socketio import join_room, leave_room

from Delivery_app_BK.services.domain.user import DRIVER_APP_SCOPE
from Delivery_app_BK.services.infra.redis import list_latest_driver_locations, set_latest_driver_location
from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.connection.auth import authenticated_socket_event, emit_socket_error
from Delivery_app_BK.sockets.contracts.realtime import (
    SERVER_EVENT_DRIVER_LOCATION_SNAPSHOT,
    SERVER_EVENT_DRIVER_LOCATION_UPDATED,
)
from Delivery_app_BK.sockets.rooms.names import build_team_driver_live_room


def subscribe_team_driver_live(claims: dict) -> None:
    team_id = claims.get("active_team_id") or claims.get("team_id")
    if team_id is None:
        emit_socket_error(code="missing_team", error="A team workspace is required for driver live.")
        return

    room = build_team_driver_live_room(team_id)
    join_room(room, sid=request.sid)

    positions = list_latest_driver_locations(int(team_id))
    socketio.emit(
        SERVER_EVENT_DRIVER_LOCATION_SNAPSHOT,
        {"positions": positions},
        room=request.sid,
    )


def unsubscribe_team_driver_live(claims: dict) -> None:
    team_id = claims.get("active_team_id") or claims.get("team_id")
    if team_id is None:
        return

    leave_room(build_team_driver_live_room(team_id), sid=request.sid)


@authenticated_socket_event
def publish_driver_location(claims: dict, data: dict | None) -> None:
    if claims.get("app_scope") != DRIVER_APP_SCOPE:
        emit_socket_error(code="forbidden_publish", error="Only driver app sessions can publish live location.")
        return

    team_id = claims.get("active_team_id") or claims.get("team_id")
    driver_id = claims.get("user_id")
    coords = (data or {}).get("coords")
    if team_id is None or driver_id is None:
        emit_socket_error(code="missing_identity", error="Live location requires user and team context.")
        return

    if not isinstance(coords, dict):
        emit_socket_error(code="invalid_coords", error="Live location coordinates are required.")
        return

    lat = coords.get("lat")
    lng = coords.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        emit_socket_error(code="invalid_coords", error="Live location coordinates must be numeric.")
        return

    timestamp = (data or {}).get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        timestamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "driver_id": int(driver_id),
        "team_id": int(team_id),
        "coords": {"lat": float(lat), "lng": float(lng)},
        "heading": (data or {}).get("heading"),
        "speed": (data or {}).get("speed"),
        "timestamp": timestamp,
    }

    set_latest_driver_location(int(team_id), int(driver_id), payload)
    socketio.emit(
        SERVER_EVENT_DRIVER_LOCATION_UPDATED,
        payload,
        room=build_team_driver_live_room(team_id),
    )
