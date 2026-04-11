from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, role_required
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.commands.notifications.delete_push_subscription import (
    delete_push_subscription as delete_push_subscription_service,
)
from Delivery_app_BK.services.commands.notifications.upsert_push_subscription import (
    upsert_push_subscription as upsert_push_subscription_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service

notifications_bp = Blueprint("api_v2_notifications_bp", __name__)


@notifications_bp.route("/push-subscriptions", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def register_push_subscription():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: upsert_push_subscription_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response({})


@notifications_bp.route("/push-subscriptions", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def remove_push_subscription():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_push_subscription_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response({})
