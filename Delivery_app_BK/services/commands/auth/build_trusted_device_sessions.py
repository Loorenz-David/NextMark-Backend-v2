from flask import current_app
from sqlalchemy.orm import joinedload

from Delivery_app_BK.errors import DomainError
from Delivery_app_BK.models import db, TrustedDevice, TrustedDeviceUser, User

from ...context import ServiceContext
from .token_utils import build_user_tokens


def _session_payload(user: User, tokens: dict) -> dict:
    return {
        "user_client_id": user.client_id,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "socket_token": tokens["socket_token"],
        "user": tokens["user"],
    }


def build_trusted_device_sessions(
    ctx: ServiceContext,
    *,
    trusted_device: TrustedDevice,
    initiating_user: User,
    app_scope: str,
    time_zone: str | None,
) -> dict:
    """Build one independent auth bundle per eligible assigned user.

    - Loads active assignments in a single query with users eagerly joined
      (no N+1).
    - Initiating user is placed first; the rest are ordered by username.
    - The initiating user's bundle must build or the whole login fails.
    - A secondary user whose bundle raises a domain error is excluded and
      counted in a single ``trusted_device_users_excluded`` warning;
      unexpected (non-domain) errors propagate and fail the login.
    - Enforces the configured per-device user cap.
    """
    assignments = (
        db.session.query(TrustedDeviceUser)
        .filter(
            TrustedDeviceUser.trusted_device_id == trusted_device.id,
            TrustedDeviceUser.is_active.is_(True),
        )
        .options(joinedload(TrustedDeviceUser.user))
        .all()
    )

    users_by_id: dict[int, User] = {}
    for assignment in assignments:
        assigned_user = assignment.user
        if assigned_user is not None:
            users_by_id[assigned_user.id] = assigned_user

    # The initiating user is guaranteed assigned (checked upstream); make sure
    # they are present even if the eager load raced.
    users_by_id[initiating_user.id] = initiating_user

    others = sorted(
        (u for uid, u in users_by_id.items() if uid != initiating_user.id),
        key=lambda u: (u.username or "").lower(),
    )
    ordered = [initiating_user, *others]

    max_users = int(current_app.config.get("MAX_USERS_PER_DEVICE", 25))
    excluded_by_cap = max(0, len(ordered) - max_users)
    ordered = ordered[:max_users]

    sessions: list[dict] = []
    excluded = 0
    for user in ordered:
        try:
            tokens = build_user_tokens(
                user,
                app_scope=app_scope,
                time_zone=time_zone,
                trusted_device=trusted_device,
            )
        except DomainError:
            if user.id == initiating_user.id:
                # The initiating user must be valid for the requested scope.
                raise
            excluded += 1
            continue
        sessions.append(_session_payload(user, tokens))

    total_excluded = excluded + excluded_by_cap
    if total_excluded:
        ctx.set_warning(
            {"code": "trusted_device_users_excluded", "count": total_excluded}
        )

    return {
        "authentication_mode": "trusted_device",
        "trusted_device": {
            "client_id": trusted_device.client_id,
            "name": trusted_device.name,
        },
        "active_user_client_id": initiating_user.client_id,
        "sessions": sessions,
    }
