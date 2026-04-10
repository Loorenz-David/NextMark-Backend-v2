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
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.queries.route_plan.list_route_plans import (
    list_route_plans as list_route_plans_service,
)
from Delivery_app_BK.services.queries.route_plan.get_plan import (
    get_plan as get_plan_service,
)
from Delivery_app_BK.services.commands.route_plan.create_plan import (
    create_plan as create_plan_service,
)
from Delivery_app_BK.services.commands.route_plan.update_plan import (
    update_plan as update_plan_service,
)

from Delivery_app_BK.services.commands.route_plan.delete_plan import (
    delete_plan as delete_plan_service,
)
from Delivery_app_BK.services.commands.route_plan.mark_plan_state import (
    mark_plan_state as mark_plan_state_service
)
from Delivery_app_BK.services.commands.route_plan.plan_states.update_plan_state import (
    update_plan_state as update_plan_state_service,
)
from Delivery_app_BK.services.queries.order.list_orders import (
    list_orders as list_orders_service,
)
from Delivery_app_BK.services.queries.route_plan.plan_states.list_plan_states import (
    list_plan_states as list_plan_states_service,
)
from Delivery_app_BK.services.queries.route_plan.route_groups.list_route_groups import (
    list_route_groups as list_route_groups_service,
)
from Delivery_app_BK.services.queries.route_plan.route_groups.get_route_group import (
    get_route_group as get_route_group_service,
)
from Delivery_app_BK.services.queries.route_solutions.get_route_solution import (
    get_route_solution_with_stops as get_route_solution_with_stops_service,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.select_route_solution import (
    select_route_solution as select_route_solution_service,
)
from Delivery_app_BK.services.commands.route_plan.materialize_route_groups import (
    materialize_route_groups as materialize_route_groups_service,
)
from Delivery_app_BK.services.commands.route_plan.create_route_group_in_plan import (
    create_route_group_in_plan as create_route_group_in_plan_service,
)
from Delivery_app_BK.services.commands.route_plan.delete_route_group import (
    delete_route_group as delete_route_group_service,
)


route_plans_bp = Blueprint("api_v2_route_plans_bp", __name__)


@route_plans_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_route_plans():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True)
    ctx = ServiceContext(
        query_params=request.args,
        incoming_data=incoming_data,
        identity=identity,
    )
  

    outcome = run_service(lambda c: list_route_plans_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/states/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_route_plan_states():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
        inject_team_id = False,
    )
    outcome = run_service(lambda c: list_plan_states_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_route_plan():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_plan_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_plan():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus = prevent_event_bus
    )
    outcome = run_service(lambda c: update_plan_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_route_plan():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_plan_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_plan(route_plan_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_plan_service(route_plan_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/orders/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_route_plan_orders(route_plan_id: int):

    identity = get_jwt()
    route_group_id = request.args.get("route_group_id", type=int)
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: list_orders_service(
            c,
            route_plan_id=route_plan_id,
            route_group_id=route_group_id,
        ),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_route_plan_route_groups(route_plan_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_route_groups_service(route_plan_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups/materialize", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def materialize_route_plan_route_groups(route_plan_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "route_plan_id": route_plan_id},
        identity=identity,
    )
    outcome = run_service(lambda c: materialize_route_groups_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_route_plan_route_group(route_plan_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "route_plan_id": route_plan_id},
        identity=identity,
    )
    outcome = run_service(lambda c: create_route_group_in_plan_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups/<int:route_group_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_plan_route_group(route_plan_id: int, route_group_id: int):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)
    outcome = run_service(
        lambda c: get_route_group_service(route_plan_id, route_group_id, c), ctx
    )
    response = Response()
    
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups/<int:route_group_id>/route-solutions/<int:route_solution_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_route_group_route_solution(route_plan_id: int, route_group_id: int, route_solution_id: int):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)
    outcome = run_service(
        lambda c: get_route_solution_with_stops_service(route_plan_id, route_group_id, route_solution_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-groups/<int:route_group_id>/route-solutions/<int:route_solution_id>/select", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def select_route_group_route_solution(route_plan_id: int, route_group_id: int, route_solution_id: int):
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


@route_plans_bp.route("/<int:route_plan_id>/route-groups/<int:route_group_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_route_plan_route_group(route_plan_id: int, route_group_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data={
            "route_plan_id": route_plan_id,
            "route_group_id": route_group_id,
        },
        identity=identity,
    )
    outcome = run_service(lambda c: delete_route_group_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/state/<int:state_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_route_plan_state(route_plan_id: int, state_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        identity=identity,
        prevent_event_bus=prevent_event_bus

    )
    outcome = run_service(
        lambda c: update_plan_state_service(c, route_plan_id, state_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@route_plans_bp.route("/<int:route_plan_id>/route-is-ready", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def mark_route_plan_ready(route_plan_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )

    outcome = run_service(
        lambda c: mark_plan_state_service(c, route_plan_id, PlanStateId.READY),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )
