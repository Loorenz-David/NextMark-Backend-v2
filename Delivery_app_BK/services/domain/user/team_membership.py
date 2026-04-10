from typing import Literal

from Delivery_app_BK.models import User

WorkspaceKind = Literal["personal", "team"]


def has_team_workspace_snapshot(user: User) -> bool:
    return (
        getattr(user, "team_workspace_team_id", None) is not None
        and getattr(user, "team_workspace_role_id", None) is not None
    )


def has_primal_workspace(user: User) -> bool:
    return (
        getattr(user, "primals_team_id", None) is not None
        and getattr(user, "primals_role_id", None) is not None
    )


def is_team_workspace_active(user: User) -> bool:
    if has_team_workspace_snapshot(user):
        return False

    if not has_primal_workspace(user):
        return False

    return (
        user.team_id != user.primals_team_id
        or user.user_role_id != user.primals_role_id
    )


def get_current_workspace(user: User) -> WorkspaceKind:
    if has_team_workspace_snapshot(user):
        return "personal"

    if is_team_workspace_active(user):
        return "team"

    return "personal"


def has_team_workspace_available(user: User) -> bool:
    return has_team_workspace_snapshot(user) or get_current_workspace(user) == "team"


def get_active_workspace_team_id(user: User) -> int | None:
    return getattr(user, "team_id", None)


def is_user_member_of_team(user: User, team_id: int | None) -> bool:
    if team_id is None:
        return False

    return (
        getattr(user, "team_id", None) == team_id
        or getattr(user, "team_workspace_team_id", None) == team_id
    )


def resolve_user_team_membership(user: User, team_id: int | None) -> dict:
    if team_id is None:
        return {
            "is_member": False,
            "is_active_workspace": False,
            "role_id": None,
            "workspace": get_current_workspace(user),
        }

    if getattr(user, "team_id", None) == team_id:
        return {
            "is_member": True,
            "is_active_workspace": True,
            "role_id": getattr(user, "user_role_id", None),
            "workspace": get_current_workspace(user),
        }

    if getattr(user, "team_workspace_team_id", None) == team_id:
        return {
            "is_member": True,
            "is_active_workspace": False,
            "role_id": getattr(user, "team_workspace_role_id", None),
            "workspace": get_current_workspace(user),
        }

    return {
        "is_member": False,
        "is_active_workspace": False,
        "role_id": None,
        "workspace": get_current_workspace(user),
    }
