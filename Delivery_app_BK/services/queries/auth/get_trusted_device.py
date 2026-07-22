from ...context import ServiceContext
from ...commands.auth.trusted_device_common import (
    load_team_device,
    load_active_assigned_users,
    serialize_device,
    serialize_assigned_user,
)


def get_trusted_device(ctx: ServiceContext, device_client_id: str):
    """Return one team device with its active assigned users. No tokens."""
    device = load_team_device(ctx, device_client_id)
    users = load_active_assigned_users(device.id)
    return {
        "trusted_device": serialize_device(device),
        "users": [serialize_assigned_user(u) for u in users],
    }
