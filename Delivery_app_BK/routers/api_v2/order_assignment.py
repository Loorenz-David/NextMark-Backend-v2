from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, role_required
from Delivery_app_BK.services.commands.order_assignment import (
    assign_order_to_plan as assign_order_to_plan_service,
)
from Delivery_app_BK.services.commands.order_assignment import (
    assign_orders_to_plan_batch as assign_orders_to_plan_batch_service,
)
from Delivery_app_BK.services.commands.order_assignment import (
    resolve_orders_selection as resolve_orders_selection_service,
)
from Delivery_app_BK.services.commands.order_assignment import (
    unassign_order_from_plan as unassign_order_from_plan_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.requests.common.types import parse_optional_int
from Delivery_app_BK.services.run_service import run_service


order_assignment_bp = Blueprint("api_v2_order_assignment_bp", __name__)


@order_assignment_bp.route("/orders/<int:order_id>/plan/<int:plan_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def assign_order_to_plan(order_id: int, plan_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    destination_route_group_id = parse_optional_int(
        incoming_data.get("route_group_id"),
        field="route_group_id",
    )
    ctx = ServiceContext(
        identity=identity,
        prevent_event_bus=prevent_event_bus,
    )

    outcome = run_service(
        lambda c: assign_order_to_plan_service(
            c,
            order_id,
            plan_id,
            destination_route_group_id=destination_route_group_id,
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


@order_assignment_bp.route("/orders/<int:order_id>/unassign-plan", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def unassign_order_from_plan(order_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        identity=identity,
        prevent_event_bus=prevent_event_bus,
    )

    outcome = run_service(lambda c: unassign_order_from_plan_service(c, order_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_assignment_bp.route("/selection/resolve", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def resolve_order_batch_selection():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(lambda c: resolve_orders_selection_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_assignment_bp.route("/plans/<int:plan_id>/batch", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def assign_orders_to_plan_batch(plan_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    destination_route_group_id = parse_optional_int(
        incoming_data.get("route_group_id"),
        field="route_group_id",
    )
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus=prevent_event_bus,
    )

    outcome = run_service(
        lambda c: assign_orders_to_plan_batch_service(
            c,
            plan_id,
            destination_route_group_id=destination_route_group_id,
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
