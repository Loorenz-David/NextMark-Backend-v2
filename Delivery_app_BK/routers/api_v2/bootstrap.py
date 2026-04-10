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
from Delivery_app_BK.services.queries.bootstrap.list_bootstrap import (
    list_bootstrap as list_bootstrap_service,
)


bootstrap_bp = Blueprint("api_v2_bootstrap_bp", __name__)


@bootstrap_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_bootstrap():
    """Return bootstrap data for admin app initialization.

    Query params:
        city_key (optional): Overrides identity default city for zones bootstrap.

    zones_context contract (v1):
        {
            "city_key": str | None,
            "selected_version": {
                "id": int,
                "version_number": int,
                "is_active": bool,
            } | None,
            "zones": [
                {
                    "id": int,
                    "name": str,
                    "zone_type": str,
                    "centroid": {"lat": float, "lng": float} | None,
                    "bbox": {
                        "min_lat": float,
                        "max_lat": float,
                        "min_lng": float,
                        "max_lng": float,
                    } | None,
                    "geometry_simplified": dict | None,
                    "is_active": bool,
                    "template_ref": {
                        "id": int,
                        "name": str,
                        "version": int,
                    } | None,
                    "has_geometry": bool,
                    "geometry_resolution": "none" | "simplified",
                }
            ],
        }

    City resolution order:
        1) query city_key
        2) identity default_city_key
        3) fallback to empty zones_context + warning
    """
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_bootstrap_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )
