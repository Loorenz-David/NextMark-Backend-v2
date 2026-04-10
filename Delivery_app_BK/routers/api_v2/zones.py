"""Zone management API endpoints.

Routes
------
GET  /api_v2/zones/                          list zone versions (filter: ?city_key=)
PUT  /api_v2/zones/                          create a new zone version
POST /api_v2/zones/ensure-first-version      ensure version 1 for city or return latest
PATCH /api_v2/zones/<version_id>/activate    activate a zone version
GET  /api_v2/zones/<version_id>/zones        list zones in a version
PUT  /api_v2/zones/<version_id>/zones        add a zone to a version
PATCH /api_v2/zones/<version_id>/zones/<zone_id>           update zone name (active or inactive)
PATCH /api_v2/zones/<version_id>/zones/<zone_id>/geometry  update zone geometry (inactive only)
"""
from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, role_required
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service

zone_bp = Blueprint("api_v2_zone_bp", __name__)


@zone_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_versions():
    identity = get_jwt()
    ctx = ServiceContext(query_params=request.args.to_dict(), identity=identity)
    from Delivery_app_BK.services.queries.zones.list_zone_versions import list_zone_versions
    outcome = run_service(lambda c: list_zone_versions(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN])
def create_version():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)
    from Delivery_app_BK.services.commands.zones.create_zone_version import create_zone_version
    outcome = run_service(lambda c: create_zone_version(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/ensure-first-version", methods=["POST"])
@jwt_required()
@role_required([ADMIN])
def ensure_first_version():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(incoming_data=incoming_data, identity=identity)
    from Delivery_app_BK.services.commands.zones.ensure_first_zone_version import (
        ensure_first_zone_version,
    )

    outcome = run_service(lambda c: ensure_first_zone_version(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/activate", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def activate_version(version_id: int):
    identity = get_jwt()
    ctx = ServiceContext(incoming_data={"version_id": version_id}, identity=identity)
    from Delivery_app_BK.services.commands.zones.activate_zone_version import activate_zone_version
    outcome = run_service(lambda c: activate_zone_version(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_zones(version_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params={**request.args.to_dict(), "version_id": version_id},
        identity=identity,
    )

    from Delivery_app_BK.services.queries.zones.list_zones_for_version import list_zones_for_version
    outcome = run_service(lambda c: list_zones_for_version(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones", methods=["PUT"])
@jwt_required()
@role_required([ADMIN])
def create_zone(version_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.create_zone import create_zone as _create_zone
    outcome = run_service(lambda c: _create_zone(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones/<int:zone_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def update_zone_name(version_id: int, zone_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.update_zone_name import (
        update_zone_name as _update_zone_name,
    )

    outcome = run_service(lambda c: _update_zone_name(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones/<int:zone_id>/geometry", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def update_zone_geometry(version_id: int, zone_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.update_zone_geometry import (
        update_zone_geometry as _update_zone_geometry,
    )

    outcome = run_service(lambda c: _update_zone_geometry(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones/<int:zone_id>", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN])
def delete_zone(version_id: int, zone_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data={"version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.delete_zone import delete_zone as _delete_zone

    outcome = run_service(lambda c: _delete_zone(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones/<int:zone_id>/template", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_zone_template(version_id: int, zone_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params={"version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.queries.zones.get_zone_template import get_zone_template

    outcome = run_service(lambda c: get_zone_template(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


@zone_bp.route("/<int:version_id>/zones/<int:zone_id>/template", methods=["PUT"])
@jwt_required()
@role_required([ADMIN])
def upsert_zone_template(version_id: int, zone_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.create_zone_template import create_zone_template

    outcome = run_service(lambda c: create_zone_template(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
