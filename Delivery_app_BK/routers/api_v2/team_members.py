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
from Delivery_app_BK.services.queries.team_members.list_team_members import (
    list_team_members as list_team_members_service,
)
from Delivery_app_BK.services.queries.team_members.get_team_member import (
    get_team_member as get_team_member_service,
)
from Delivery_app_BK.services.commands.team_members.leave_team import (
    leave_team as leave_team_service,
)
from Delivery_app_BK.services.commands.team_members.kick_team_memember import (
    kick_team_memember as kick_team_memember_service,
)
from Delivery_app_BK.services.commands.team_members.change_memeber_user_role import (
    change_memeber_user_role as change_memeber_user_role_service,
)
from Delivery_app_BK.services.commands.team.update_team_name import (
    update_team_name as update_team_name_service
)


team_bp = Blueprint("api_v2_team_bp", __name__)


@team_bp.route("/members/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_team_members():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: list_team_members_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_bp.route("/members/<int:user_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_team_member(user_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args,
        identity=identity,
    )
    outcome = run_service(lambda c: get_team_member_service(user_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_bp.route("/members/leave/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def leave_team():
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: leave_team_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@team_bp.route("/members/kick/<int:user_id>", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def kick_team_memember(user_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: kick_team_memember_service(c, user_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@team_bp.route("/members/role/", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def change_memeber_user_role():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: change_memeber_user_role_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@team_bp.route("/change-name", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def change_team_name():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_team_name_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
