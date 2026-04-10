from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, DRIVER, role_required
from Delivery_app_BK.services.commands.costumer.create_costumer import (
    create_costumer as create_costumer_service,
)
from Delivery_app_BK.services.commands.costumer.delete_costumer import (
    delete_costumer as delete_costumer_service,
)
from Delivery_app_BK.services.commands.costumer.update_costumer import (
    update_costumer as update_costumer_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.costumer import (
    list_costumers as list_costumers_service,
    get_costumer as get_costumer_service,
    list_costumer_orders as list_costumer_orders_service,
)
from Delivery_app_BK.services.run_service import run_service


costumer_bp = Blueprint("api_v2_costumer_bp", __name__)


@costumer_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_costumers():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_costumers_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )

@costumer_bp.route("/<int:costumer_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_costumer(costumer_id):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: get_costumer_service( costumer_id, c ), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@costumer_bp.route("/<int:costumer_id>/orders", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_costumer_orders(costumer_id):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_costumer_orders_service(costumer_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@costumer_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_costumer():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_costumer_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@costumer_bp.route("/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_costumer():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_costumer_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@costumer_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_costumer():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_costumer_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )
