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
from Delivery_app_BK.services.queries.user_role_rule.list_user_role_rules import (
    list_user_role_rules as list_user_role_rules_service,
)
from Delivery_app_BK.services.queries.user_role_rule.list_date_range_access_rules import (
    list_date_range_access_rules as list_date_range_access_rules_service,
)
from Delivery_app_BK.services.queries.user_role_rule.get_date_range_access_rule import (
    get_date_range_access_rule as get_date_range_access_rule_service,
)
from Delivery_app_BK.services.queries.user_role_rule.list_order_state_transition_rules import (
    list_order_state_transition_rules as list_order_state_transition_rules_service,
)
from Delivery_app_BK.services.queries.user_role_rule.get_order_state_transition_rule import (
    get_order_state_transition_rule as get_order_state_transition_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    create_date_range_access_rule as create_date_range_access_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    update_date_range_access_rule as update_date_range_access_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    delete_date_range_access_rule as delete_date_range_access_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    create_order_state_transition_rule as create_order_state_transition_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    update_order_state_transition_rule as update_order_state_transition_rule_service,
)
from Delivery_app_BK.services.commands.user_role_rule import (
    delete_order_state_transition_rule as delete_order_state_transition_rule_service,
)


user_role_rule_bp = Blueprint("api_v2_user_role_rule_bp", __name__)


@user_role_rule_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_user_role_rules():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_user_role_rules_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/<int:user_role_id>/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_user_role_rules_by_role(user_role_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: list_user_role_rules_service(c, user_role_id=user_role_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/date_range/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_date_range_access_rules():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_date_range_access_rules_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/date_range/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_date_range_access_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: create_date_range_access_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/date_range/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_date_range_access_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: update_date_range_access_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/date_range/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_date_range_access_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: delete_date_range_access_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/date_range/<int:rule_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_date_range_access_rule(rule_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_date_range_access_rule_service(rule_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/order_state/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_order_state_transition_rules():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: list_order_state_transition_rules_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/order_state/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_order_state_transition_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: create_order_state_transition_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/order_state/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_order_state_transition_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: update_order_state_transition_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/order_state/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_order_state_transition_rule():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(
        lambda c: delete_order_state_transition_rule_service(c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@user_role_rule_bp.route("/order_state/<int:rule_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_order_state_transition_rule(rule_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_order_state_transition_rule_service(rule_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
