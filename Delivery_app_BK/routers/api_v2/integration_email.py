from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.commands.integration_email.connect_email import (
    connect_email,
)
from Delivery_app_BK.services.queries.integration_email.get_email_details import (
    get_email_details,
)
from Delivery_app_BK.services.commands.integration_email.update_email_config import (
    update_email_config,
)
from Delivery_app_BK.services.commands.integration_email.disconnect_email import (
    disconnect_email,
)
from Delivery_app_BK.routers.http.response import Response


email_bp = Blueprint("api_v2_integration_email", __name__)


@email_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect_email_integration():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: connect_email(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@email_bp.route("/<integration_id>", methods=["GET"])
@jwt_required()
def get_email_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: get_email_details(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@email_bp.route("/<integration_id>", methods=["PATCH"])
@jwt_required()
def update_email_integration(integration_id: str):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_email_config(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@email_bp.route("/<integration_id>", methods=["DELETE"])
@jwt_required()
def delete_email_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: disconnect_email(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
