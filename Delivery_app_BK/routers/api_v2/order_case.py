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
from Delivery_app_BK.services.queries.order.order_cases.order_chats.list_case_chats import (
    list_case_chats as list_case_chats_service,
)
from Delivery_app_BK.services.queries.order.order_cases.order_chats.get_case_chat import (
    get_case_chat as get_case_chat_service,
)
from Delivery_app_BK.services.queries.order.order_cases.order_chats.list_unseen_case_chats import (
    list_unseen_case_chats as list_unseen_case_chats_service,
)
from Delivery_app_BK.services.commands.order.order_case.order_chat.create_case_chat import (
    create_case_chat as create_case_chat_service,
)
from Delivery_app_BK.services.commands.order.order_case.order_chat.update_case_chat import (
    update_case_chat as update_case_chat_service,
)
from Delivery_app_BK.services.commands.order.order_case.order_chat.delete_case_chat import (
    delete_case_chat as delete_case_chat_service,
)
from Delivery_app_BK.services.commands.notifications.create_notification_read import (
    create_notification_read as create_case_chat_read_service,
)
from Delivery_app_BK.services.commands.notifications.mark_order_case_chats_read import (
    mark_order_case_chats_read as mark_order_case_chats_read_service,
)
from Delivery_app_BK.services.queries.order.order_cases.list_order_cases import (
    list_order_cases as list_order_cases_service,
)
from Delivery_app_BK.services.queries.order.order_cases.get_order_case import (
    get_order_case as get_order_case_service,
)
from Delivery_app_BK.services.commands.order.order_case.create_order_case import (
    create_order_case as create_order_case_service,
)
from Delivery_app_BK.services.commands.order.order_case.update_order_case import (
    update_order_case as update_order_case_service,
)
from Delivery_app_BK.services.commands.order.order_case.delete_order_case import (
    delete_order_case as delete_order_case_service,
)
from Delivery_app_BK.services.commands.order.order_case.update_order_case_state import (
    update_order_case_state as update_order_case_state_service,
)


order_case_bp = Blueprint("api_v2_order_case_bp", __name__)


@order_case_bp.route("/case_chats/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def list_case_chats():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_case_chats_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/unseen/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def list_unseen_case_chats():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_unseen_case_chats_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/<int:case_chat_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def get_case_chat(case_chat_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_case_chat_service(case_chat_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def create_case_chat():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_case_chat_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def update_case_chat():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_case_chat_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def delete_case_chat():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_case_chat_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@order_case_bp.route("/case_chats/<int:case_chat_id>/read/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def create_case_chat_read(case_chat_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(
        lambda c: create_case_chat_read_service(c, case_chat_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/<int:order_case_id>/read/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def mark_order_case_read(order_case_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(
        lambda c: mark_order_case_chats_read_service(c, order_case_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def list_order_cases():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_order_cases_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/<int:order_case_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def get_order_case(order_case_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_order_case_service(order_case_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def create_order_case():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: create_order_case_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_case_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def update_order_case():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_order_case_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@order_case_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def delete_order_case():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_order_case_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@order_case_bp.route("/<int:order_case_id>/state", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT, DRIVER])
def update_order_case_state(order_case_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    payload = {
        "target": {
            "target_id": order_case_id,
            "fields": incoming_data or {},
        }
    }
    ctx.incoming_data = payload
    outcome = run_service(lambda c: update_order_case_state_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
