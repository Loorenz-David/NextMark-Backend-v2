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
from Delivery_app_BK.services.queries.content_templates.label.list_label_templates import (
    list_label_templates as list_label_templates_service,
)
from Delivery_app_BK.services.queries.content_templates.label.get_label_template import (
    get_label_template as get_label_template_service,
)
from Delivery_app_BK.services.commands.label_template.create_print_template import (
    create_label_template as create_label_template_service,
)
from Delivery_app_BK.services.commands.label_template.update_print_template import (
    update_label_template as update_label_template_service,
)
from Delivery_app_BK.services.commands.label_template.delete_print_template import (
    delete_label_template as delete_label_template_service,
)
from Delivery_app_BK.services.commands.label_template.toggle_template_state import (
    toggle_template_state as toggle_template_state_service,
)

label_template_bp = Blueprint("api_v2_label_template_bp", __name__)


@label_template_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_label_templates():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_label_templates_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@label_template_bp.route("/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_label_template():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        extract_fields_key=False
    )
    outcome = run_service(lambda c: create_label_template_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@label_template_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_label_template():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_label_template_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )

@label_template_bp.route("/<int:template_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def toggle_template_state(template_id):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: toggle_template_state_service(c, template_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )



@label_template_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_label_template():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: delete_label_template_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@label_template_bp.route("/<int:template_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_label_template(template_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_label_template_service(template_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
