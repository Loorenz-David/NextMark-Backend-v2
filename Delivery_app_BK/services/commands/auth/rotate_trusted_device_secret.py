from datetime import datetime, timezone

from Delivery_app_BK.models import db
from Delivery_app_BK.services.domain.auth import (
    generate_device_secret,
    hash_device_secret,
)

from ...context import ServiceContext
from .trusted_device_common import load_team_device, serialize_device
from .trusted_device_audit import (
    record_trusted_device_event,
    DEVICE_SECRET_ROTATED,
    RESULT_SUCCESS,
)


def rotate_trusted_device_secret(ctx: ServiceContext, device_client_id: str):
    """Issue a new device secret, returning the plaintext exactly once."""
    device = load_team_device(ctx, device_client_id)

    raw_secret = generate_device_secret()
    device.device_secret_hash = hash_device_secret(raw_secret)
    device.updated_at = datetime.now(timezone.utc)

    record_trusted_device_event(
        ctx,
        event_name=DEVICE_SECRET_ROTATED,
        result=RESULT_SUCCESS,
        trusted_device=device,
    )
    db.session.commit()

    return {
        "trusted_device": serialize_device(device),
        "device_secret": raw_secret,
    }
