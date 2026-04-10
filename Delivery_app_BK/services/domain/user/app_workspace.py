from typing import Literal

from Delivery_app_BK.errors import PermissionDenied, ValidationFailed
from Delivery_app_BK.models import BaseRole, Team, User, UserRole, db

WorkspaceKind = Literal["personal", "team"]
AppScope = Literal["admin", "driver"]

PERSONAL_WORKSPACE: WorkspaceKind = "personal"
TEAM_WORKSPACE: WorkspaceKind = "team"
ADMIN_APP_SCOPE: AppScope = "admin"
DRIVER_APP_SCOPE: AppScope = "driver"
ALLOWED_APP_SCOPES = {ADMIN_APP_SCOPE, DRIVER_APP_SCOPE}
ADMIN_APP_TEAM_ROLES = {"admin", "assistant"}


def parse_app_scope(value) -> AppScope:
    if not isinstance(value, str):
        raise ValidationFailed("app_scope is required.")

    normalized = value.strip().lower()
    if normalized not in ALLOWED_APP_SCOPES:
        raise ValidationFailed("app_scope must be 'admin' or 'driver'.")

    return normalized


def parse_workspace_kind(value, *, field: str = "target_workspace") -> WorkspaceKind:
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be 'personal' or 'team'.")

    normalized = value.strip().lower()
    if normalized not in {PERSONAL_WORKSPACE, TEAM_WORKSPACE}:
        raise ValidationFailed(f"{field} must be 'personal' or 'team'.")

    return normalized


def get_app_workspace_attribute(app_scope: AppScope) -> str:
    parse_app_scope(app_scope)
    return f"{app_scope}_app_current_workspace"


def get_personal_workspace_assignment(user: User) -> tuple[int | None, int | None]:
    team_id = getattr(user, "primals_team_id", None) or getattr(user, "team_id", None)
    role_id = getattr(user, "primals_role_id", None) or getattr(user, "user_role_id", None)
    return team_id, role_id


def get_team_workspace_assignment(user: User) -> tuple[int | None, int | None]:
    snapshot_team_id = getattr(user, "team_workspace_team_id", None)
    snapshot_role_id = getattr(user, "team_workspace_role_id", None)
    if snapshot_team_id is not None and snapshot_role_id is not None:
        return snapshot_team_id, snapshot_role_id

    active_team_id = getattr(user, "team_id", None)
    active_role_id = getattr(user, "user_role_id", None)
    personal_team_id, personal_role_id = get_personal_workspace_assignment(user)

    if active_team_id is None or active_role_id is None:
        return None, None

    if active_team_id == personal_team_id and active_role_id == personal_role_id:
        return None, None

    return active_team_id, active_role_id


def has_team_workspace_available_for_app(user: User) -> bool:
    team_id, role_id = get_team_workspace_assignment(user)
    return team_id is not None and role_id is not None


def get_stored_app_workspace(user: User, app_scope: AppScope) -> WorkspaceKind | None:
    raw = getattr(user, get_app_workspace_attribute(app_scope), None)
    if raw in {PERSONAL_WORKSPACE, TEAM_WORKSPACE}:
        return raw
    return None


def get_default_app_workspace(user: User, app_scope: AppScope) -> WorkspaceKind:
    if app_scope == ADMIN_APP_SCOPE:
        return PERSONAL_WORKSPACE

    if has_team_workspace_available_for_app(user):
        return TEAM_WORKSPACE

    return PERSONAL_WORKSPACE


def set_app_current_workspace(user: User, app_scope: AppScope, workspace: WorkspaceKind) -> None:
    setattr(user, get_app_workspace_attribute(app_scope), parse_workspace_kind(workspace))


def _load_role(role_id: int | None) -> UserRole | None:
    if role_id is None:
        return None
    return db.session.get(UserRole, role_id)


def _load_team(team_id: int | None) -> Team | None:
    if team_id is None:
        return None
    return db.session.get(Team, team_id)


def resolve_app_workspace_context(user: User, app_scope: AppScope) -> dict:
    app_scope = parse_app_scope(app_scope)
    has_team_workspace = has_team_workspace_available_for_app(user)
    workspace = get_stored_app_workspace(user, app_scope) or get_default_app_workspace(user, app_scope)

    personal_team_id, personal_role_id = get_personal_workspace_assignment(user)
    team_team_id, team_role_id = get_team_workspace_assignment(user)

    if workspace == TEAM_WORKSPACE:
        if not has_team_workspace or team_team_id is None or team_role_id is None:
            workspace = PERSONAL_WORKSPACE
        elif app_scope == ADMIN_APP_SCOPE:
            team_role = _load_role(team_role_id)
            base_role_name = ((team_role.base_role.role_name if team_role and team_role.base_role else "") or "").lower()
            if base_role_name not in ADMIN_APP_TEAM_ROLES:
                workspace = PERSONAL_WORKSPACE

    if workspace == TEAM_WORKSPACE:
        active_team_id = team_team_id
        active_role_id = team_role_id
    else:
        active_team_id = personal_team_id
        active_role_id = personal_role_id

    active_role = _load_role(active_role_id)
    active_base_role: BaseRole | None = active_role.base_role if active_role else None
    active_team = _load_team(active_team_id)

    return {
        "app_scope": app_scope,
        "current_workspace": workspace,
        "has_team_workspace": has_team_workspace,
        "active_team_id": active_team_id,
        "active_role_id": active_role_id,
        "active_role": active_role,
        "base_role_id": active_base_role.id if active_base_role else None,
        "base_role": ((active_base_role.role_name if active_base_role else "") or "").lower() or None,
        "team_name": active_team.name if active_team else None,
        "team_time_zone": active_team.time_zone if active_team else None,
        "default_country_code": active_team.default_country_code if active_team else None,
        "default_city_key": active_team.default_city_key if active_team else None,
    }


def ensure_app_workspace_state(user: User, app_scope: AppScope) -> dict:
    context = resolve_app_workspace_context(user, app_scope)
    set_app_current_workspace(user, app_scope, context["current_workspace"])
    return context


def sync_all_app_workspace_states(user: User) -> None:
    for app_scope in (ADMIN_APP_SCOPE, DRIVER_APP_SCOPE):
        ensure_app_workspace_state(user, app_scope)


def require_team_workspace_access(user: User, app_scope: AppScope) -> dict:
    context = resolve_app_workspace_context(user, app_scope)
    if not context["has_team_workspace"]:
        raise ValidationFailed("No team workspace is available for this user.")

    if app_scope == ADMIN_APP_SCOPE and context["base_role"] not in ADMIN_APP_TEAM_ROLES:
        raise PermissionDenied("Current team workspace cannot access the admin app.")

    return context
