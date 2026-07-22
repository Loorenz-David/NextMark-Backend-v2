"""Security-audit writer for trusted-device operations.

Inserts a ``TrustedDeviceEvent`` row directly (no event bus). Never persists
secrets, passwords, or tokens; ``detail`` must contain only non-sensitive
context. The caller owns the surrounding transaction/commit.
"""

from Delivery_app_BK.models import db, TrustedDeviceEvent

# Event-name constants.
DEVICE_REGISTERED = "trusted_device.registered"
DEVICE_UPDATED = "trusted_device.updated"
DEVICE_REVOKED = "trusted_device.revoked"
DEVICE_SECRET_ROTATED = "trusted_device.secret_rotated"
USER_ASSIGNED = "trusted_device.user_assigned"
USER_REMOVED = "trusted_device.user_removed"
LOGIN_SUCCEEDED = "trusted_device.login_succeeded"
LOGIN_FAILED = "trusted_device.login_failed"
SESSIONS_RESYNCED = "trusted_device.sessions_resynced"
REFRESH_REJECTED = "trusted_device.refresh_rejected"

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"


def record_trusted_device_event(
    ctx,
    *,
    event_name: str,
    result: str,
    trusted_device=None,
    target_user_id=None,
    detail: dict | None = None,
) -> TrustedDeviceEvent:
    row = TrustedDeviceEvent(
        event_name=event_name,
        result=result,
        trusted_device_id=trusted_device.id if trusted_device is not None else None,
        initiating_user_id=ctx.user_id,
        target_user_id=target_user_id,
        request_ip=getattr(ctx, "request_ip", None),
        user_agent=getattr(ctx, "user_agent", None),
        detail=detail,
        team_id=ctx.team_id,
    )
    db.session.add(row)
    return row
