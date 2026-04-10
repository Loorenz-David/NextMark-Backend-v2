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
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops.update_route_stop_position import (
    update_route_stop_position as update_route_stop_position_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops.update_route_stop_group_position import (
    update_route_stop_group_position as update_route_stop_group_position_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops.update_route_stop_service_time import (
    update_route_stop_service_time as update_route_stop_service_time_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops.mark_route_stop_actual_arrival_time import (
    mark_route_stop_actual_arrival_time as mark_route_stop_actual_arrival_time_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops.mark_route_stop_actual_departure_time import (
    mark_route_stop_actual_departure_time as mark_route_stop_actual_departure_time_service,
)
from Delivery_app_BK.errors import ValidationFailed


from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.select_route_solution import (
    select_route_solution as select_route_solution_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.mark_route_solution_actual_start_time import (
    mark_route_solution_actual_start_time as mark_route_solution_actual_start_time_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.mark_route_solution_actual_end_time import (
    mark_route_solution_actual_end_time as mark_route_solution_actual_end_time_service,
)
from Delivery_app_BK.services.queries.route_solutions.get_route_solution import (
    get_route_solution as get_route_solution_service,
)
from Delivery_app_BK.route_optimization.orchestrator import (
    optimize_route_plan,
)


route_solution_bp = Blueprint("api_v2_route_solution_bp", __name__)


@route_solution_bp.route(
    "/stops/<int:route_stop_id>/position/<int:position>",
    methods=["PATCH"],
)
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_stop_position(
    route_stop_id: int,
    position: int,
):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)
    
    outcome = run_service(
        lambda c: update_route_stop_position_service(
            c,
            route_stop_id,
            position,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route(
    "/stops/group-position",
    methods=["PATCH"],
)
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_stop_group_position():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(
        lambda c: update_route_stop_group_position_service(
            c,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route(
    "/stops/<int:route_stop_id>/service-time",
    methods=["PATCH"],
)
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_stop_service_time(route_stop_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(
        lambda c: update_route_stop_service_time_service(
            c,
            route_stop_id,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route(
    "/stops/<int:route_stop_id>/actual-arrival-time",
    methods=["PATCH"],
)
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def mark_route_stop_actual_arrival_time(route_stop_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(
        lambda c: mark_route_stop_actual_arrival_time_service(
            c,
            route_stop_id,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route(
    "/stops/<int:route_stop_id>/actual-departure-time",
    methods=["PATCH"],
)
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def mark_route_stop_actual_departure_time(route_stop_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(
        lambda c: mark_route_stop_actual_departure_time_service(
            c,
            route_stop_id,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )







@route_solution_bp.route("/<int:route_solution_id>/select", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def select_route_solution(route_solution_id: int):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)
    outcome = run_service(
        lambda c: select_route_solution_service(c, route_solution_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route("/<int:route_solution_id>/actual-start-time", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def mark_route_solution_actual_start_time(route_solution_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: mark_route_solution_actual_start_time_service(
            c,
            route_solution_id,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route("/<int:route_solution_id>/actual-end-time", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def mark_route_solution_actual_end_time(route_solution_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: mark_route_solution_actual_end_time_service(
            c,
            route_solution_id,
            incoming_data,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route("/<int:route_solution_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_solution(route_solution_id: int):
    identity = get_jwt()
    return_stops = request.args.get("return_stops", "false").lower() == "true"
    ctx = ServiceContext(identity=identity)
    outcome = run_service(
        lambda c: get_route_solution_service(route_solution_id, c, return_stops),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route("/optimize", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_route_optimization():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    if incoming_data.get("route_group_id") is None:
        return Response().build_unsuccessful_response(
            ValidationFailed("Missing route_group_id. Use canonical key 'route_group_id' for optimization."),
        )
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = optimize_route_plan(ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@route_solution_bp.route("/optimize", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_optimization():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    if incoming_data.get("route_group_id") is None:
        return Response().build_unsuccessful_response(
            ValidationFailed("Missing route_group_id. Use canonical key 'route_group_id' for optimization."),
        )
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    response = Response()
   
    
    outcome = optimize_route_plan(ctx)

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )
