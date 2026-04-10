from functools import wraps
from typing import Callable

from flask import current_app, request
from flask_socketio import disconnect
import jwt

from Delivery_app_BK.services.domain.user import ALLOWED_APP_SCOPES
from Delivery_app_BK.sockets.contracts.realtime import SERVER_EVENT_REALTIME_ERROR
from Delivery_app_BK.socketio_instance import socketio


def emit_socket_error(*, code: str, error: str) -> None:
    socketio.emit(
        SERVER_EVENT_REALTIME_ERROR,
        {"code": code, "error": error},
        room=request.sid,
    )


def _extract_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    query_token = request.args.get("token")
    if query_token:
        return query_token.strip()

    return None


def verify_socket_claims(*, disconnect_on_failure: bool = True) -> dict | None:
    token = _extract_token()
    if not token:
        if disconnect_on_failure:
            disconnect()
        else:
            emit_socket_error(code="missing_token", error="Socket token is required.")
        return None

    try:
        decoded = jwt.decode(
            token,
            current_app.config.get("JWT_SECRET_KEY"),
            algorithms=[current_app.config.get("JWT_ALGORITHM", "HS256")],
        )
    except Exception:
        if disconnect_on_failure:
            disconnect()
        else:
            emit_socket_error(code="invalid_token", error="Socket token is invalid.")
        return None

    if not decoded.get("user_id") or not decoded.get("session_scope_id"):
        if disconnect_on_failure:
            disconnect()
        else:
            emit_socket_error(code="invalid_claims", error="Socket session claims are incomplete.")
        return None

    app_scope = decoded.get("app_scope")
    if app_scope not in ALLOWED_APP_SCOPES:
        if disconnect_on_failure:
            disconnect()
        else:
            emit_socket_error(code="invalid_app_scope", error="Socket app scope is not allowed.")
        return None

    return decoded


def authenticated_socket_event(fn: Callable):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        claims = verify_socket_claims(disconnect_on_failure=False)
        if not claims:
            return None
        return fn(claims, *args, **kwargs)

    return wrapper
