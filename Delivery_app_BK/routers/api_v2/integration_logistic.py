from flask import Blueprint, jsonify, request as flask_request

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.commands.integration_logistic.auth.verify_api_key import (
    verify_api_key,
)
from Delivery_app_BK.services.commands.integration_logistic.inbound.item_placed import (
    item_placed,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import (
    parse_item_placed_request,
)
from Delivery_app_BK.services.run_service import run_service


logistic_bp = Blueprint("api_v2_integration_logistic", __name__)


@logistic_bp.route("/events/item-placed", methods=["POST"])
def inbound_item_placed():
    response = Response()

    try:
        verify_api_key(dict(flask_request.headers))
    except Exception:
        return jsonify({"error": "Unauthorized", "code": ValidationFailed.code}), 401

    raw = flask_request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=raw)
    outcome = run_service(lambda c: item_placed(parse_item_placed_request(raw)), ctx)

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
