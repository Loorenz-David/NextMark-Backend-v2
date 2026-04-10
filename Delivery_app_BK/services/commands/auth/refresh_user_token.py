from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import User, db

from ...context import ServiceContext
from .token_utils import build_user_tokens


def refresh_user_token(ctx: ServiceContext):
    identity = ctx.identity or {}
    user_id = identity.get("user_id")
    app_scope = identity.get("app_scope")
    session_scope_id = identity.get("session_scope_id")

    if user_id is None:
        raise ValidationFailed("Refresh token is missing user identity.")
    if not app_scope or not session_scope_id:
        raise ValidationFailed("Legacy refresh tokens are no longer supported. Please sign in again.")

    user = db.session.get(User, user_id)
    if not user:
        raise NotFound("User not found for refresh token.")

    tokens = build_user_tokens(
        user,
        app_scope=app_scope,
        session_scope_id=session_scope_id,
        time_zone=identity.get("time_zone"),
    )
    db.session.commit()

    return {
        "access_token": tokens["access_token"],
    }
