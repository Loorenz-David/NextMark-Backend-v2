from datetime import datetime, timezone

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import db, TrustedDeviceUser

from ...context import ServiceContext
from .trusted_device_common import load_team_device, load_team_user_by_client_id
from .trusted_device_audit import (
    record_trusted_device_event,
    USER_REMOVED,
    RESULT_SUCCESS,
)


def remove_trusted_device_user(
    ctx: ServiceContext, device_client_id: str, user_client_id: str
):
    """Revoke a user's assignment to a trusted device.

    The user's trusted-device refresh tokens stop working on next refresh.
    """
    device = load_team_device(ctx, device_client_id)
    user = load_team_user_by_client_id(ctx, user_client_id)

    assignment = (
        db.session.query(TrustedDeviceUser)
        .filter(
            TrustedDeviceUser.trusted_device_id == device.id,
            TrustedDeviceUser.user_id == user.id,
            TrustedDeviceUser.is_active.is_(True),
        )
        .first()
    )
    if assignment is None:
        raise NotFound("Active assignment was not found.")

    now = datetime.now(timezone.utc)
    assignment.is_active = False
    assignment.revoked_at = now
    assignment.revoked_by_user_id = ctx.user_id

    record_trusted_device_event(
        ctx,
        event_name=USER_REMOVED,
        result=RESULT_SUCCESS,
        trusted_device=device,
        target_user_id=user.id,
    )
    db.session.commit()

    return {}
