from flask import Blueprint, request

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.commands.user_registration.register_user import (
    register_user as register_user_service,
)


user_registration_bp = Blueprint("api_v2_user_registration_bp", __name__)


@user_registration_bp.route("/", methods=["POST"])
def register_user():
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        inject_team_id=False,
        skip_id_instance_injection=False,
        check_team_id = False
    )
    outcome = run_service(lambda c: register_user_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
