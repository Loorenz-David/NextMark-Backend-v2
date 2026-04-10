from datetime import timedelta
from uuid import uuid4

from flask_jwt_extended import create_access_token, create_refresh_token

from Delivery_app_BK.models import User
from Delivery_app_BK.services.domain.user import (
    ensure_app_workspace_state,
    parse_app_scope,
)


def _build_auth_claims(
    user: User,
    *,
    app_scope: str,
    session_scope_id: str,
    time_zone: str | None,
) -> tuple[dict, dict]:
    workspace_context = ensure_app_workspace_state(user, parse_app_scope(app_scope))
    effective_time_zone = time_zone or workspace_context["team_time_zone"] or "UTC"

    claims = {
        "user_id": user.id,
        "team_id": workspace_context["active_team_id"],
        "active_team_id": workspace_context["active_team_id"],
        "user_role_id": workspace_context["active_role_id"],
        "role_id": workspace_context["active_role_id"],
        "base_role_id": workspace_context["base_role_id"],
        "base_role": workspace_context["base_role"],
        "current_workspace": workspace_context["current_workspace"],
        "has_team_workspace": workspace_context["has_team_workspace"],
        "app_scope": app_scope,
        "session_scope_id": session_scope_id,
        "time_zone": effective_time_zone,
        "default_country_code": workspace_context["default_country_code"],
        "default_city_key": workspace_context["default_city_key"],
    }

    user_object = {
        "username": user.username,
        "profile_picture": user.profile_picture,
        "user_role_id": workspace_context["active_role_id"],
        "base_role_id": workspace_context["base_role_id"],
        "base_role": workspace_context["base_role"],
        "current_workspace": workspace_context["current_workspace"],
        "has_team_workspace": workspace_context["has_team_workspace"],
        "show_app_tutorial": user.show_app_tutorial,
        "id": user.id,
        "email": user.email,
        "teamId": workspace_context["active_team_id"],
        "active_team_id": workspace_context["active_team_id"],
        "team_name": workspace_context["team_name"],
        "default_country_code": workspace_context["default_country_code"],
        "default_city_key": workspace_context["default_city_key"],
        "app_scope": app_scope,
        "session_scope_id": session_scope_id,
    }

    return claims, user_object


def build_user_tokens(
    user: User,
    *,
    app_scope: str,
    session_scope_id: str | None = None,
    time_zone: str | None = None,
) -> dict:
    identity_data = str(user.id)
    resolved_scope = parse_app_scope(app_scope)
    resolved_session_scope_id = session_scope_id or str(uuid4())
    claims, user_object = _build_auth_claims(
        user,
        app_scope=resolved_scope,
        session_scope_id=resolved_session_scope_id,
        time_zone=time_zone,
    )

    access_token = create_access_token(identity=identity_data, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity_data, additional_claims=claims)
    socket_token = create_access_token(
        identity=identity_data,
        additional_claims=claims,
        expires_delta=timedelta(hours=24),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "socket_token": socket_token,
        "user": user_object,
    }
