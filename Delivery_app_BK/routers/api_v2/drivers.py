from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, DRIVER, role_required
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.drivers.list_active_routes import (
    list_active_routes as list_active_routes_service,
)
from Delivery_app_BK.services.queries.drivers.get_active_route import (
    get_active_route as get_active_route_service,
)
from Delivery_app_BK.services.queries.drivers.get_active_route_freshness import (
    get_active_route_freshness as get_active_route_freshness_service,
)
from Delivery_app_BK.services.queries.drivers.get_driver_bootstrap import (
    get_driver_bootstrap as get_driver_bootstrap_service,
)
from Delivery_app_BK.services.commands.drivers.complete_driver_order import (
    complete_driver_order as complete_driver_order_service,
)
from Delivery_app_BK.services.commands.drivers.fail_driver_order import (
    fail_driver_order as fail_driver_order_service,
)
from Delivery_app_BK.services.commands.drivers.undo_driver_order_terminal import (
    undo_driver_order_terminal as undo_driver_order_terminal_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_route_actual_start_time import (
    mark_driver_route_actual_start_time as mark_driver_route_actual_start_time_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_route_actual_end_time_expected import (
    mark_driver_route_actual_end_time_expected as mark_driver_route_actual_end_time_expected_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_route_actual_end_time_last_order import (
    mark_driver_route_actual_end_time_last_order as mark_driver_route_actual_end_time_last_order_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_route_actual_end_time_manual import (
    mark_driver_route_actual_end_time_manual as mark_driver_route_actual_end_time_manual_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_stop_actual_arrival_time import (
    mark_driver_stop_actual_arrival_time as mark_driver_stop_actual_arrival_time_service,
)
from Delivery_app_BK.services.commands.drivers.mark_driver_stop_actual_departure_time import (
    mark_driver_stop_actual_departure_time as mark_driver_stop_actual_departure_time_service,
)
from Delivery_app_BK.services.commands.drivers.switch_driver_workspace import (
    switch_driver_workspace as switch_driver_workspace_service,
)
from Delivery_app_BK.services.commands.drivers.adjust_driver_route_dates_to_today import (
    adjust_driver_route_dates_to_today as adjust_driver_route_dates_to_today_service,
)
from Delivery_app_BK.services.run_service import run_service


drivers_bp = Blueprint("api_v2_drivers_bp", __name__)


@drivers_bp.route("/routes/active", methods=["GET"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def list_active_routes():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )

    outcome = run_service(lambda c: list_active_routes_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/routes/<int:route_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def get_active_route(route_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )

    outcome = run_service(lambda c: get_active_route_service(route_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/routes/<int:route_id>/freshness", methods=["GET"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def get_active_route_freshness(route_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )

    outcome = run_service(lambda c: get_active_route_freshness_service(route_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/bootstrap", methods=["GET"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def get_driver_bootstrap():
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)

    outcome = run_service(lambda c: get_driver_bootstrap_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/orders/<int:order_id>/complete", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def complete_driver_order(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)

    outcome = run_service(lambda c: complete_driver_order_service(c, order_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/orders/<int:order_id>/fail", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def fail_driver_order(order_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(lambda c: fail_driver_order_service(c, order_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/orders/<int:order_id>/undo-terminal", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def undo_driver_order_terminal(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(identity=identity)

    outcome = run_service(lambda c: undo_driver_order_terminal_service(c, order_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@drivers_bp.route("/routes/<int:route_id>/actual-start-time", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_route_actual_start_time(route_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_route_actual_start_time_service(c, route_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/routes/<int:route_id>/actual-end-time/expected", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_route_actual_end_time_expected(route_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_route_actual_end_time_expected_service(c, route_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/routes/<int:route_id>/actual-end-time/last-order", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_route_actual_end_time_last_order(route_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_route_actual_end_time_last_order_service(c, route_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/routes/<int:route_id>/actual-end-time/manual", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_route_actual_end_time_manual(route_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_route_actual_end_time_manual_service(c, route_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/routes/<int:route_id>/adjust-dates-to-today", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def adjust_driver_route_dates_to_today(route_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: adjust_driver_route_dates_to_today_service(c, route_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/stops/<string:stop_client_id>/actual-arrival-time", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_stop_actual_arrival_time(stop_client_id: str):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_stop_actual_arrival_time_service(c, stop_client_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/stops/<string:stop_client_id>/actual-departure-time", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def mark_driver_stop_actual_departure_time(stop_client_id: str):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(
        lambda c: mark_driver_stop_actual_departure_time_service(c, stop_client_id, c.incoming_data),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@drivers_bp.route("/workspace/switch", methods=["POST"])
@jwt_required()
@role_required([ADMIN, DRIVER])
def switch_driver_workspace():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)

    outcome = run_service(lambda c: switch_driver_workspace_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
