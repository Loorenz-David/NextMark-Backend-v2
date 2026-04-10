from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.queries.integrations.list_active_integrations import (
    list_active_integrations,
)
from Delivery_app_BK.routers.http.response import Response


integrations_bp = Blueprint("api_v2_integrations", __name__)


@integrations_bp.route("/", methods=["GET"])
@jwt_required()
def list_integrations():

    identity = get_jwt()
    ctx = ServiceContext(identity=identity)

    outcome = run_service(lambda c: list_active_integrations(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
