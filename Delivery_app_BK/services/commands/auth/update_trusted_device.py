from datetime import datetime, timezone

from Delivery_app_BK.models import db

from ...context import ServiceContext
from ...requests.auth.trusted_device import parse_update_trusted_device
from .trusted_device_common import load_team_device, serialize_device
from .trusted_device_audit import (
    record_trusted_device_event,
    DEVICE_UPDATED,
    RESULT_SUCCESS,
)


def update_trusted_device(ctx: ServiceContext, device_client_id: str):
    """Rename and/or enable/disable a trusted device."""
    request = parse_update_trusted_device(ctx.incoming_data)
    device = load_team_device(ctx, device_client_id)

    if "name" in request.provided_fields:
        device.name = request.name
    if "is_active" in request.provided_fields:
        device.is_active = request.is_active

    device.updated_at = datetime.now(timezone.utc)

    record_trusted_device_event(
        ctx,
        event_name=DEVICE_UPDATED,
        result=RESULT_SUCCESS,
        trusted_device=device,
        detail={"fields": sorted(request.provided_fields)},
    )
    db.session.commit()

    return {"trusted_device": serialize_device(device)}
