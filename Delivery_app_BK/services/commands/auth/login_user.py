from Delivery_app_BK.models import db, User
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.auth import (
    resolve_trusted_device,
    is_user_assigned_to_device,
)

from ...context import ServiceContext
from ...requests.auth.login import parse_login_request
from .token_utils import build_user_tokens
from .build_trusted_device_sessions import build_trusted_device_sessions


def login_user_service( ctx:ServiceContext ):

    target_user = ctx.incoming_data
    if not target_user:
        raise ValidationFailed("Missing username and password.")

    login_request = parse_login_request(target_user)
    user_query = db.session.query( User )
    user:User = user_query.filter( User.email == login_request.email ).first()

    if not user:
        raise ValidationFailed( "Incorrect login information." )

    if not user.check_password( login_request.password ):
        raise ValidationFailed( "Incorrect login information." )

    # Raises on invalid/revoked device credentials; None when none were sent.
    trusted_device = resolve_trusted_device(ctx)

    # Device enrollment is an added capability, not a whitelist: a user who is
    # not assigned to the device still signs in normally from it, receiving only
    # their own tokens and never the multi-user bundle.
    if trusted_device is None or not is_user_assigned_to_device(
        user.id, trusted_device.id
    ):
        tokens = build_user_tokens(
            user,
            app_scope=login_request.app_scope,
            time_zone=login_request.time_zone,
        )
        db.session.commit()
        return {
            "authentication_mode": "single_user",
            **tokens,
        }

    payload = build_trusted_device_sessions(
        ctx,
        trusted_device=trusted_device,
        initiating_user=user,
        app_scope=login_request.app_scope,
        time_zone=login_request.time_zone,
    )
    db.session.commit()
    return payload
