from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, TrustedDeviceUser

from ...context import ServiceContext
from ...requests.auth.trusted_device import parse_assign_trusted_device_user
from .trusted_device_common import (
    load_team_device,
    load_team_user_by_client_id,
    serialize_assigned_user,
)
from .trusted_device_audit import (
    record_trusted_device_event,
    USER_ASSIGNED,
    RESULT_SUCCESS,
)


def assign_trusted_device_user(ctx: ServiceContext, device_client_id: str):
    """Assign a user to a trusted device (idempotent-reactivating)."""
    request = parse_assign_trusted_device_user(ctx.incoming_data)
    device = load_team_device(ctx, device_client_id)
    user = load_team_user_by_client_id(ctx, request.user_client_id)

    existing = (
        db.session.query(TrustedDeviceUser)
        .filter(
            TrustedDeviceUser.trusted_device_id == device.id,
            TrustedDeviceUser.user_id == user.id,
        )
        .first()
    )

    if existing is not None:
        if existing.is_active:
            raise ValidationFailed("User is already assigned to this device.")
        # Reactivate a previously revoked assignment.
        existing.is_active = True
        existing.revoked_at = None
        existing.revoked_by_user_id = None
        existing.created_by_user_id = ctx.user_id
        existing.created_at = datetime.now(timezone.utc)
    else:
        db.session.add(
            TrustedDeviceUser(
                trusted_device_id=device.id,
                user_id=user.id,
                is_active=True,
                created_by_user_id=ctx.user_id,
            )
        )

    record_trusted_device_event(
        ctx,
        event_name=USER_ASSIGNED,
        result=RESULT_SUCCESS,
        trusted_device=device,
        target_user_id=user.id,
    )
    db.session.commit()

    return {"assigned_user": serialize_assigned_user(user)}
