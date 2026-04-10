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
from Delivery_app_BK.services.overviews.local_delivery_overview import (
    local_delivery_overview as local_delivery_overview_service,
)


route_plan_overviews_bp = Blueprint("api_v2_route_plan_overviews_bp", __name__)


@route_plan_overviews_bp.route("/<int:route_plan_id>/route_group/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_group_overview(route_plan_id: int):
    print(f"Received request for route group overview of plan {route_plan_id}")
    identity = get_jwt()
    ctx = ServiceContext(identity=identity, query_params=dict(request.args))
    outcome = run_service(
        lambda c: local_delivery_overview_service(c, route_plan_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
