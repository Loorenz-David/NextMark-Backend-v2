from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import role_required, ADMIN
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.commands.auth.login_user import (
    login_user_service,
)
from Delivery_app_BK.services.commands.auth.refresh_user_token import (
    refresh_user_token,
)
from Delivery_app_BK.services.commands.auth.refresh_socket_token import (
    refresh_socket_token,
)
from Delivery_app_BK.services.commands.auth.register_trusted_device import (
    register_trusted_device,
)
from Delivery_app_BK.services.commands.auth.update_trusted_device import (
    update_trusted_device,
)
from Delivery_app_BK.services.commands.auth.revoke_trusted_device import (
    revoke_trusted_device,
)
from Delivery_app_BK.services.commands.auth.rotate_trusted_device_secret import (
    rotate_trusted_device_secret,
)
from Delivery_app_BK.services.commands.auth.assign_trusted_device_user import (
    assign_trusted_device_user,
)
from Delivery_app_BK.services.commands.auth.remove_trusted_device_user import (
    remove_trusted_device_user,
)
from Delivery_app_BK.services.queries.auth.list_trusted_devices import (
    list_trusted_devices,
)
from Delivery_app_BK.services.queries.auth.get_trusted_device import (
    get_trusted_device,
)
from Delivery_app_BK.services.commands.auth.get_trusted_device_users import (
    get_trusted_device_users,
)
from Delivery_app_BK.services.commands.auth.resync_trusted_device_sessions import (
    resync_trusted_device_sessions,
)
from Delivery_app_BK.services.domain.auth import (
    TRUSTED_DEVICE_ID_HEADER,
    TRUSTED_DEVICE_SECRET_HEADER,
)


def _device_headers() -> dict:
    return {
        "trusted_device_client_id": request.headers.get(TRUSTED_DEVICE_ID_HEADER),
        "trusted_device_secret": request.headers.get(TRUSTED_DEVICE_SECRET_HEADER),
    }


def _admin_ctx(**kwargs) -> ServiceContext:
    """Build a ServiceContext for an admin management route, carrying JWT
    identity plus request metadata for audit trails."""
    return ServiceContext(
        identity=get_jwt(),
        request_ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        **kwargs,
    )


def _respond(outcome, ctx, *, success_payload=None):
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    payload = outcome.data if success_payload is None else success_payload
    return response.build_successful_response(payload, warnings=ctx.warnings)


auth_bp = Blueprint("api_v2_auth_bp", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity={},
        request_ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        trusted_device_client_id=request.headers.get(TRUSTED_DEVICE_ID_HEADER),
        trusted_device_secret=request.headers.get(TRUSTED_DEVICE_SECRET_HEADER),
    )

    outcome = run_service(lambda c: login_user_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@auth_bp.route("/refresh_token", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt()
    
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: refresh_user_token(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@auth_bp.route("/refresh_socket_token", methods=["POST"])
@jwt_required(refresh=True)
def refresh_socket():
    identity = get_jwt()

    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: refresh_socket_token(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


# ----------------------------------------------------------------------
# Trusted-device administration (ADMIN only)
# ----------------------------------------------------------------------


@auth_bp.route("/trusted-devices", methods=["POST"])
@jwt_required()
@role_required([ADMIN])
def register_trusted_device_route():
    ctx = _admin_ctx(incoming_data=request.get_json(silent=True) or {})
    outcome = run_service(lambda c: register_trusted_device(c), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices", methods=["GET"])
@jwt_required()
@role_required([ADMIN])
def list_trusted_devices_route():
    ctx = _admin_ctx(query_params=request.args)
    outcome = run_service(lambda c: list_trusted_devices(c), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices/<device_client_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN])
def get_trusted_device_route(device_client_id: str):
    ctx = _admin_ctx(query_params=request.args)
    outcome = run_service(lambda c: get_trusted_device(c, device_client_id), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices/<device_client_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def update_trusted_device_route(device_client_id: str):
    ctx = _admin_ctx(incoming_data=request.get_json(silent=True) or {})
    outcome = run_service(lambda c: update_trusted_device(c, device_client_id), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices/<device_client_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN])
def revoke_trusted_device_route(device_client_id: str):
    ctx = _admin_ctx()
    outcome = run_service(lambda c: revoke_trusted_device(c, device_client_id), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices/<device_client_id>/secret", methods=["POST"])
@jwt_required()
@role_required([ADMIN])
def rotate_trusted_device_secret_route(device_client_id: str):
    ctx = _admin_ctx()
    outcome = run_service(lambda c: rotate_trusted_device_secret(c, device_client_id), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-devices/<device_client_id>/users", methods=["POST"])
@jwt_required()
@role_required([ADMIN])
def assign_trusted_device_user_route(device_client_id: str):
    ctx = _admin_ctx(incoming_data=request.get_json(silent=True) or {})
    outcome = run_service(lambda c: assign_trusted_device_user(c, device_client_id), ctx)
    return _respond(outcome, ctx)


@auth_bp.route(
    "/trusted-devices/<device_client_id>/users/<user_client_id>", methods=["DELETE"]
)
@jwt_required()
@role_required([ADMIN])
def remove_trusted_device_user_route(device_client_id: str, user_client_id: str):
    ctx = _admin_ctx()
    outcome = run_service(
        lambda c: remove_trusted_device_user(c, device_client_id, user_client_id), ctx
    )
    return _respond(outcome, ctx)


# ----------------------------------------------------------------------
# Trusted-device runtime endpoints (device-credential authenticated)
# ----------------------------------------------------------------------


@auth_bp.route("/trusted-device/users", methods=["GET"])
def trusted_device_users_route():
    # Device credentials only — no user JWT. Returns assigned users, no tokens.
    ctx = ServiceContext(
        identity={},
        request_ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        **_device_headers(),
    )
    outcome = run_service(lambda c: get_trusted_device_users(c), ctx)
    return _respond(outcome, ctx)


@auth_bp.route("/trusted-device/sessions/refresh", methods=["POST"])
@jwt_required()
def trusted_device_sessions_refresh_route():
    # Device credentials + an authenticated assigned user (access token).
    ctx = ServiceContext(
        identity=get_jwt(),
        request_ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        **_device_headers(),
    )
    outcome = run_service(lambda c: resync_trusted_device_sessions(c), ctx)
    return _respond(outcome, ctx)
