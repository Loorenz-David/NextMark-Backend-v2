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
from Delivery_app_BK.services.queries.user_role.list_user_roles import (
    list_user_roles as list_user_roles_service,
)
from Delivery_app_BK.services.queries.user_role_rule import (
    list_user_role_rules as list_user_role_rules_service,
)
from Delivery_app_BK.services.queries.user_role.get_user_role import (
    get_user_role as get_user_role_service,
)
from Delivery_app_BK.services.commands.user_role.create_user_role import (
    create_user_role as create_user_role_service,
)
from Delivery_app_BK.services.commands.user_role.update_user_role import (
    update_user_role as update_user_role_service,
)
from Delivery_app_BK.services.commands.user_role.delete_user_role import (
    delete_user_role as delete_user_role_service,
)


user_role_bp = Blueprint("api_v2_user_role_bp", __name__)


@user_role_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_user_roles():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_user_roles_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_bp.route("/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_user_role():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_user_role_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_user_role():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_user_role_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_user_role():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_user_role_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_bp.route("/<int:role_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_user_role(role_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_user_role_service(role_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_bp.route("/<int:role_id>/rules/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_user_role_rules(role_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: list_user_role_rules_service(c, user_role_id=role_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
