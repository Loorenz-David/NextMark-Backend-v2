from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.commands.integration_twilio.connect_twilio import (
    connect_twilio,
)
from Delivery_app_BK.services.queries.integration_twilio.get_twilio_details import (
    get_twilio_details,
)
from Delivery_app_BK.services.commands.integration_twilio.update_twilio_config import (
    update_twilio_config,
)
from Delivery_app_BK.services.commands.integration_twilio.disconnect_twilio import (
    disconnect_twilio,
)
from Delivery_app_BK.routers.http.response import Response


twilio_bp = Blueprint("api_v2_integration_twilio", __name__)


@twilio_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect_twilio_integration():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: connect_twilio(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@twilio_bp.route("/<integration_id>", methods=["GET"])
@jwt_required()
def get_twilio_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: get_twilio_details(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@twilio_bp.route("/<integration_id>", methods=["PATCH"])
@jwt_required()
def update_twilio_integration(integration_id: str):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_twilio_config(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@twilio_bp.route("/<integration_id>", methods=["DELETE"])
@jwt_required()
def delete_twilio_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: disconnect_twilio(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
