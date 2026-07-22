from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.services.domain.auth import resolve_trusted_device

from ...context import ServiceContext
from .trusted_device_common import (
    load_active_assigned_users,
    serialize_assigned_user,
)


def get_trusted_device_users(ctx: ServiceContext):
    """List users assigned to the presenting trusted device. No tokens.

    Authenticated by device credentials only (no user JWT required). Stamps
    ``last_used_at`` on the device, so it commits.
    """
    device = resolve_trusted_device(ctx)
    if device is None:
        raise ValidationFailed("Trusted-device authentication failed.")

    users = load_active_assigned_users(device.id)
    db.session.commit()

    return {
        "trusted_device": {"client_id": device.client_id, "name": device.name},
        "users": [serialize_assigned_user(u) for u in users],
    }
