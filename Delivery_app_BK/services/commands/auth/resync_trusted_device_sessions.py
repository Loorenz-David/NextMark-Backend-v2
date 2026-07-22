from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, User
from Delivery_app_BK.services.domain.auth import (
    resolve_trusted_device,
    is_user_assigned_to_device,
)

from ...context import ServiceContext
from .build_trusted_device_sessions import build_trusted_device_sessions
from .trusted_device_audit import (
    record_trusted_device_event,
    SESSIONS_RESYNCED,
    RESULT_SUCCESS,
)


def resync_trusted_device_sessions(ctx: ServiceContext):
    """Rebuild fresh session bundles for all currently authorized users.

    Requires valid device credentials AND an authenticated assigned user
    (access JWT). Used at startup / explicit sync / recovery — not on every
    account switch. Returns the same shape as trusted-device login.
    """
    device = resolve_trusted_device(ctx)
    if device is None:
        raise ValidationFailed("Trusted-device authentication failed.")

    user_id = ctx.user_id
    app_scope = ctx.app_scope
    if user_id is None or not app_scope:
        raise ValidationFailed("A valid session is required to resynchronize.")

    user = db.session.get(User, user_id)
    if user is None or not is_user_assigned_to_device(user.id, device.id):
        raise ValidationFailed("Trusted-device session is no longer valid.")

    payload = build_trusted_device_sessions(
        ctx,
        trusted_device=device,
        initiating_user=user,
        app_scope=app_scope,
        time_zone=ctx.time_zone,
    )

    record_trusted_device_event(
        ctx,
        event_name=SESSIONS_RESYNCED,
        result=RESULT_SUCCESS,
        trusted_device=device,
        target_user_id=user.id,
    )
    db.session.commit()

    return payload
