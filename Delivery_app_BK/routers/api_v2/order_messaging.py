"""
Router for manually triggered order messaging.

  Authenticated (admin):
    POST /api_v2/order_messages/send → send or resend a message template to one
                                       or more orders on the channels configured
                                       for that template's business event.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import (
    role_required,
    ADMIN,
    ASSISTANT,
)
from Delivery_app_BK.services.commands.order.messaging.send_manual_message import (
    send_manual_order_message as send_manual_order_message_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service


order_messaging_bp = Blueprint("order_messaging", __name__)


@order_messaging_bp.route("/send", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def send_manual_order_message():
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data=request.get_json(silent=True) or {},
        identity=identity,
    )
    outcome = run_service(send_manual_order_message_service, ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
