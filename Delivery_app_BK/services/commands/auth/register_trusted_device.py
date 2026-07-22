from datetime import datetime, timezone

from Delivery_app_BK.models import db, TrustedDevice, TrustedDeviceUser
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.domain.auth import (
    generate_device_secret,
    hash_device_secret,
)

from ...context import ServiceContext
from ...requests.auth.trusted_device import parse_register_trusted_device
from .trusted_device_common import (
    load_team_user_by_client_id,
    serialize_device,
)
from .trusted_device_audit import (
    record_trusted_device_event,
    DEVICE_REGISTERED,
    USER_ASSIGNED,
    RESULT_SUCCESS,
)


def register_trusted_device(ctx: ServiceContext):
    """Register a trusted device for the caller's team and assign users.

    Returns the device metadata and the plaintext secret exactly once.
    """
    request = parse_register_trusted_device(ctx.incoming_data)

    raw_secret = generate_device_secret()
    device = TrustedDevice(
        client_id=generate_client_id("tdv"),
        name=request.name,
        device_secret_hash=hash_device_secret(raw_secret),
        is_active=True,
        team_id=ctx.team_id,
        registered_by_user_id=ctx.user_id,
    )
    db.session.add(device)
    db.session.flush()  # assign device.id for assignments + audit

    record_trusted_device_event(
        ctx, event_name=DEVICE_REGISTERED, result=RESULT_SUCCESS, trusted_device=device
    )

    assigned_count = 0
    for user_client_id in request.user_client_ids:
        user = load_team_user_by_client_id(ctx, user_client_id)
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
        assigned_count += 1

    device.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "trusted_device": serialize_device(device),
        "device_secret": raw_secret,
        "assigned_user_count": assigned_count,
    }
