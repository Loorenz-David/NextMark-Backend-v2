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
from Delivery_app_BK.services.queries.team_invitation.sent.list_team_invites_sent import (
    list_team_invites_sent as list_team_invites_sent_service,
)
from Delivery_app_BK.services.queries.team_invitation.sent.get_team_invite_sent import (
    get_team_invite_sent as get_team_invite_sent_service,
)
from Delivery_app_BK.services.queries.team_invitation.received.list_team_invites_received import (
    list_team_invites_received as list_team_invites_received_service,
)
from Delivery_app_BK.services.queries.team_invitation.received.get_team_invite_received import (
    get_team_invite_received as get_team_invite_received_service,
)
from Delivery_app_BK.services.commands.team_invitation.create_team_invitation import (
    create_team_invitation as create_team_invitation_service,
)
from Delivery_app_BK.services.commands.team_invitation.accept_team_invitation import (
    accept_team_invitation as accept_team_invitation_service,
)
from Delivery_app_BK.services.commands.team_invitation.delete_team_invitation import (
    delete_team_invitation as delete_team_invitation_service,
)


team_invitation_bp = Blueprint("api_v2_team_invitation_bp", __name__)


@team_invitation_bp.route("/sent/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_team_invites_sent():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_team_invites_sent_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/sent/<int:invite_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_team_invite_sent(invite_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_team_invite_sent_service(invite_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/received/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_team_invites_received():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_team_invites_received_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/received/<int:invite_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_team_invite_received(invite_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(
        lambda c: get_team_invite_received_service(invite_id, c),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_team_invitation():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )

    outcome = run_service(lambda c: create_team_invitation_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/accept/<int:invite_id>", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def accept_team_invitation(invite_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(
        lambda c: accept_team_invitation_service(c, invite_id),
        ctx,
    )
    
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_invitation_bp.route("/<int:invite_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_team_invitation(invite_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(
        lambda c: delete_team_invitation_service(c, invite_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
