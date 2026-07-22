from datetime import datetime, timezone

from Delivery_app_BK.models import db

from ...context import ServiceContext
from .trusted_device_common import load_team_device, serialize_device
from .trusted_device_audit import (
    record_trusted_device_event,
    DEVICE_REVOKED,
    RESULT_SUCCESS,
)


def revoke_trusted_device(ctx: ServiceContext, device_client_id: str):
    """Revoke a trusted device.

    Blocks new login bundles and resync immediately. Trusted-device refresh
    tokens stop working on their next refresh (enforce-on-refresh), so access
    ends within the access-token TTL without a JWT blocklist.
    """
    device = load_team_device(ctx, device_client_id)

    now = datetime.now(timezone.utc)
    device.is_active = False
    if device.revoked_at is None:
        device.revoked_at = now
        device.revoked_by_user_id = ctx.user_id
    device.updated_at = now

    record_trusted_device_event(
        ctx,
        event_name=DEVICE_REVOKED,
        result=RESULT_SUCCESS,
        trusted_device=device,
    )
    db.session.commit()

    return {"trusted_device": serialize_device(device)}
