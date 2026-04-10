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
from Delivery_app_BK.services.queries.item_state.list_item_states import (
    list_item_states as list_item_states_service,
)
from Delivery_app_BK.services.queries.item_state.get_item_state import (
    get_item_state as get_item_state_service,
)
from Delivery_app_BK.services.commands.item.create.create_item_state import (
    create_item_state as create_item_state_service,
)
from Delivery_app_BK.services.commands.item.update.update_item_state import (
    update_item_state as update_item_state_service,
)
from Delivery_app_BK.services.commands.item.update.update_item_state_index import (
    update_item_state_index as update_item_state_index_service,
)
from Delivery_app_BK.services.commands.item.delete.delete_item_state import (
    delete_item_state as delete_item_state_service,
)


item_state_bp = Blueprint("api_v2_item_state_bp", __name__)


@item_state_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_item_states():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_item_states_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_state_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_item_state():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_item_state_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_state_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_item_state():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_item_state_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@item_state_bp.route("/<int:state_id>/index/<int:new_index>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_item_state_index(state_id: int, new_index: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(
        lambda c: update_item_state_index_service(c, state_id, new_index),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@item_state_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_item_state():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_item_state_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@item_state_bp.route("/<int:state_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_item_state(state_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_item_state_service(state_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@item_state_bp.route("/<int:state_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_item_state_by_id(state_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data={"target_id": state_id},
        identity=identity,
    )
    outcome = run_service(lambda c: delete_item_state_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response({}, warnings=ctx.warnings)
