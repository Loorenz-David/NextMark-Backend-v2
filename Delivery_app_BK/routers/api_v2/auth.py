from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.routers.http.response import Response
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


auth_bp = Blueprint("api_v2_auth_bp", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity={},
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
