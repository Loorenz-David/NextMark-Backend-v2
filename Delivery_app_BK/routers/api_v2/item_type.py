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
from Delivery_app_BK.services.queries.item_type.list_item_types import (
    list_item_types as list_item_types_service,
)
from Delivery_app_BK.services.queries.item_type.get_item_type import (
    get_item_type as get_item_type_service,
)
from Delivery_app_BK.services.commands.item.create.create_item_type import (
    create_item_type as create_item_type_service,
)
from Delivery_app_BK.services.commands.item.update.update_item_type import (
    update_item_type as update_item_type_service,
)
from Delivery_app_BK.services.commands.item.delete.delete_item_type import (
    delete_item_type as delete_item_type_service,
)


item_type_bp = Blueprint("api_v2_item_type_bp", __name__)


@item_type_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_item_types():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_item_types_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_type_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_item_type():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_item_type_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_type_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_item_type():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_item_type_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@item_type_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_item_type():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_item_type_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@item_type_bp.route("/<int:type_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_item_type(type_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_item_type_service(type_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_type_bp.route("/<int:type_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_item_type_by_id(type_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data={"target_id": type_id},
        identity=identity,
    )
    outcome = run_service(lambda c: delete_item_type_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response({}, warnings=ctx.warnings)
