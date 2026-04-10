import os
from flask import Blueprint, request

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Team
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.commands.seed import seed_initial_data as seed_initial_data_service
from Delivery_app_BK.services.commands.test_data import (
    clear_generated_test_data,
    create_test_data,
)


seed_bp = Blueprint("api_v2_seed_bp", __name__)

SECRETE_KEY = os.getenv("SECRET_KEY")


def _is_valid(key) -> bool:
    if not SECRETE_KEY:
        return False
    return SECRETE_KEY == key


def _require_key(data: dict, response: Response):
    """Return the key validation error response, or None if valid."""
    key = data.get("key")
    if not key:
        return response.build_unsuccessful_response(ValidationFailed("Missing key"))
    if not _is_valid(key):
        return response.build_unsuccessful_response(
            ValidationFailed("Failed, seed endpoint only available on development")
        )
    return None


@seed_bp.route("/", methods=["POST"])
def seed():
    response = Response()
    data = request.get_json(silent=True) or {}

    if not data:
        return response.build_unsuccessful_response(
            ValidationFailed("Missing payload with key")
        )

    err = _require_key(data, response)
    if err:
        return err

    ctx = ServiceContext(
        incoming_data=data,
        inject_team_id=False,
        check_team_id=False,
        skip_id_instance_injection=False,
    )

    outcome = run_service(lambda c: seed_initial_data_service(c), ctx)

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@seed_bp.route("/test-data", methods=["POST"])
def seed_test_data():
    """Trigger the test-data orchestrator.

    Required body fields:
        key         (str)  — secret key
        team_id     (int)  — the team to seed data for
        user_id     (int)  — used as driver_id on route solutions

    Optional identity fields (forwarded verbatim into ServiceContext.identity):
        active_team_id     (int)
        role_id            (int)
        base_role_id       (int)
        time_zone          (str)  e.g. "Europe/Stockholm"
        default_country_code (str) e.g. "SE"

    All other body keys are forwarded as ``incoming_data`` to the orchestrator
    (plan_data, order_data, item_types_data, route_solution_settings_data, …).
    """
    response = Response()
    data = request.get_json(silent=True) or {}

    if not data:
        return response.build_unsuccessful_response(
            ValidationFailed("Missing request body")
        )

    err = _require_key(data, response)
    if err:
        return err

    # --- resolve required targeting fields ---
    team_id = data.get("team_id")
    user_id = data.get("user_id")

    if not team_id:
        return response.build_unsuccessful_response(
            ValidationFailed("team_id is required")
        )
    if not isinstance(team_id, int) or team_id <= 0:
        return response.build_unsuccessful_response(
            ValidationFailed("team_id must be a positive integer")
        )

    if not user_id:
        return response.build_unsuccessful_response(
            ValidationFailed("user_id is required")
        )
    if not isinstance(user_id, int) or user_id <= 0:
        return response.build_unsuccessful_response(
            ValidationFailed("user_id must be a positive integer")
        )

    # --- build identity (mirrors JWT claims shape used throughout the app) ---
    identity = {
        "team_id": team_id,
        "active_team_id": data.get("active_team_id", team_id),
        "user_id": user_id,
        "role_id": data.get("role_id"),
        "base_role_id": data.get("base_role_id"),
        "time_zone": data.get("time_zone"),
        "default_country_code": data.get("default_country_code"),
    }
    # strip None values so ServiceContext property lookups behave identically
    # to a real JWT payload that simply omits absent claims
    identity = {k: v for k, v in identity.items() if v is not None}

    # --- build orchestrator incoming_data (everything except meta/targeting keys) ---
    _META_KEYS = {"key", "team_id", "user_id", "active_team_id", "role_id",
                  "base_role_id", "time_zone", "default_country_code"}
    incoming_data = {k: v for k, v in data.items() if k not in _META_KEYS}

    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        inject_team_id=True,
        check_team_id=True,
        skip_id_instance_injection=True,
        relationship_map={"team_id": Team},
        prevent_event_bus=True,
    )

    outcome = run_service(lambda c: create_test_data(c.identity, c.incoming_data), ctx)

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@seed_bp.route("/test-data/cleanup", methods=["POST"])
def cleanup_test_data():
    """Delete test data created by the test-data orchestrator for a team.

    Required body fields:
        key         (str)  — secret key
        team_id     (int)  — team whose seeded test data should be removed

    Optional identity fields:
        user_id             (int)
        active_team_id      (int)
        role_id             (int)
        base_role_id        (int)
        time_zone           (str)
        default_country_code (str)

    Optional cleanup knobs (forwarded in incoming_data):
        order_reference_prefix (str) default: "test-"
        item_name_prefix       (str) default: "test-"
        additional_plan_labels (list[str])
    """
    response = Response()
    data = request.get_json(silent=True) or {}

    return _run_cleanup_test_data(data, response)


@seed_bp.route("/test-data", methods=["DELETE"])
def cleanup_test_data_rest():
    """REST-style cleanup variant for seeded test data.

    Uses the same payload and validation as POST /api_v2/seed/test-data/cleanup.
    """
    response = Response()
    data = request.get_json(silent=True) or {}

    return _run_cleanup_test_data(data, response)


def _run_cleanup_test_data(data: dict, response: Response):
    """Run test-data cleanup with shared validation and context building."""

    if not data:
        return response.build_unsuccessful_response(
            ValidationFailed("Missing request body")
        )

    err = _require_key(data, response)
    if err:
        return err

    team_id = data.get("team_id")
    if not team_id:
        return response.build_unsuccessful_response(
            ValidationFailed("team_id is required")
        )
    if not isinstance(team_id, int) or team_id <= 0:
        return response.build_unsuccessful_response(
            ValidationFailed("team_id must be a positive integer")
        )

    user_id = data.get("user_id")
    if user_id is not None and (not isinstance(user_id, int) or user_id <= 0):
        return response.build_unsuccessful_response(
            ValidationFailed("user_id must be a positive integer when provided")
        )

    identity = {
        "team_id": team_id,
        "active_team_id": data.get("active_team_id", team_id),
        "user_id": user_id,
        "role_id": data.get("role_id"),
        "base_role_id": data.get("base_role_id"),
        "time_zone": data.get("time_zone"),
        "default_country_code": data.get("default_country_code"),
    }
    identity = {k: v for k, v in identity.items() if v is not None}

    _META_KEYS = {
        "key",
        "team_id",
        "user_id",
        "active_team_id",
        "role_id",
        "base_role_id",
        "time_zone",
        "default_country_code",
    }
    incoming_data = {k: v for k, v in data.items() if k not in _META_KEYS}

    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        inject_team_id=True,
        check_team_id=True,
        skip_id_instance_injection=True,
        relationship_map={"team_id": Team},
        prevent_event_bus=True,
    )

    outcome = run_service(lambda c: clear_generated_test_data(c), ctx)

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )
