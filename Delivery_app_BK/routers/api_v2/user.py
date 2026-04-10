from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.routers.utils.role_decorator import (
    role_required,
    ADMIN,
    ASSISTANT,
    DRIVER,
)
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.queries.user.get_user_profile import (
    get_user_profile as get_user_profile_service,
)
from Delivery_app_BK.services.commands.user.update_user import (
    update_user as update_user_service,
)
from Delivery_app_BK.services.commands.user.switch_user_workspace import (
    switch_user_workspace as switch_user_workspace_service,
)


user_bp = Blueprint("api_v2_user_bp", __name__)


@user_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_user_profile():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_user_profile_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_user_profile():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_user_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_bp.route("/workspace/switch", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def switch_user_workspace():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: switch_user_workspace_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
