from Delivery_app_BK.models import db, TrustedDevice, TrustedDeviceUser

from ...context import ServiceContext
from ...commands.auth.trusted_device_common import serialize_device


def list_trusted_devices(ctx: ServiceContext):
    """List the caller's team trusted devices with active-assignment counts."""
    devices = (
        db.session.query(TrustedDevice)
        .filter(TrustedDevice.team_id == ctx.team_id)
        .order_by(TrustedDevice.created_at.desc())
        .all()
    )

    counts: dict[int, int] = {}
    if devices:
        rows = (
            db.session.query(TrustedDeviceUser.trusted_device_id)
            .filter(
                TrustedDeviceUser.trusted_device_id.in_([d.id for d in devices]),
                TrustedDeviceUser.is_active.is_(True),
            )
            .all()
        )
        for (device_id,) in rows:
            counts[device_id] = counts.get(device_id, 0) + 1

    return {
        "trusted_devices": [
            {**serialize_device(device), "active_user_count": counts.get(device.id, 0)}
            for device in devices
        ]
    }
