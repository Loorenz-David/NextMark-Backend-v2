from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, role_required
from Delivery_app_BK.services.commands.route_plan.local_delivery.update_settings import (
    update_route_group_settings as update_route_group_settings_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.plan_types.get_route_group import (
    get_route_group_plan_type as get_route_group_plan_type_service,
)
from Delivery_app_BK.services.run_service import run_service


route_groups_bp = Blueprint("api_v2_route_groups_bp", __name__)


@route_groups_bp.route("/settings", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_group_settings():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus=prevent_event_bus,
    )
    outcome = run_service(
        lambda c: update_route_group_settings_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_groups_bp.route("/route_plans/<int:route_plan_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_group_plan_type(route_plan_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_route_group_plan_type_service(route_plan_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
