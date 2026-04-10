from functools import wraps
from typing import Iterable

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from Delivery_app_BK.errors import PermissionDenied, ValidationFailed
from Delivery_app_BK.routers.http.response import Response

ADMIN = 1
ASSISTANT = 2
DRIVER = 3


def _build_error_response(error):
    response = Response()
    return response.build_unsuccessful_response(error)


def _validate_app_scope(required_scope: str | Iterable[str]):
    claims = get_jwt()
    app_scope = claims.get("app_scope")

    if app_scope is None:
        raise ValidationFailed("App scope not found in token.")

    if isinstance(required_scope, str):
        allowed_scopes = {required_scope}
    else:
        allowed_scopes = set(required_scope)

    if app_scope not in allowed_scopes:
        raise PermissionDenied("This session is not allowed to access the requested app surface.")

def role_required(allowed_roles: Iterable[int] | None = None):
    """
    Decorator to enforce role-based access using the base_role_id stored in JWT claims.
    Usage:
        @jwt_required()
        @role_required([ADMIN, ASSISTANT])
        def my_route(): ...
    """

    allowed_set = set(allowed_roles or [])

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Ensure a valid JWT is present even if @jwt_required is omitted.
            verify_jwt_in_request(optional=False)
            claims = get_jwt()
            response = Response()

            base_role_id = claims.get("base_role_id")
            if base_role_id is None:
                return response.build_unsuccessful_response(
                    ValidationFailed("Role not found in token.")
                )

            if allowed_set and base_role_id not in allowed_set:
                return response.build_unsuccessful_response(
                    PermissionDenied("Insufficient role permissions.")
                )

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def app_scope_required(required_scope: str | Iterable[str]):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request(optional=False)

            try:
                _validate_app_scope(required_scope)
            except (PermissionDenied, ValidationFailed) as error:
                return _build_error_response(error)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def install_blueprint_scope_guard(blueprint: Blueprint, required_scope: str | Iterable[str]):
    if getattr(blueprint, "_app_scope_guard_installed", False):
        return blueprint

    @blueprint.before_request
    def _guard_scope():
        if "Authorization" not in request.headers:
            return None

        try:
            verify_jwt_in_request(optional=False)
            _validate_app_scope(required_scope)
        except (PermissionDenied, ValidationFailed) as error:
            return _build_error_response(error)

        return None

    blueprint._app_scope_guard_installed = True
    return blueprint
