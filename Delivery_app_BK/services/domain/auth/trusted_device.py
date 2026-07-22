"""Trusted-device authentication primitives.

Responsibilities:
- generate a high-entropy device secret;
- hash/verify that secret with a server-side pepper using constant-time
  comparison (the codebase's HMAC idiom, matching ``verify_api_key``);
- resolve the trusted device presented on a request from its headers.

The raw device secret is never stored, logged, or placed on incoming_data.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from flask import current_app

from Delivery_app_BK.models import db, TrustedDevice, TrustedDeviceUser
from Delivery_app_BK.errors import ValidationFailed


TRUSTED_DEVICE_ID_HEADER = "X-Trusted-Device-Id"
TRUSTED_DEVICE_SECRET_HEADER = "X-Trusted-Device-Secret"

# Generic message; internal reasons are never exposed to the caller.
_AUTH_FAILED_MESSAGE = "Trusted-device authentication failed."
_SESSION_INVALID_MESSAGE = "Trusted-device session is no longer valid."


def _pepper() -> str:
    pepper = current_app.config.get("TRUSTED_DEVICE_SECRET_PEPPER")
    if not pepper:
        # Should be impossible given the default.py fallback, but never hash
        # an unpeppered secret silently.
        raise ValidationFailed(_AUTH_FAILED_MESSAGE)
    return pepper


def generate_device_secret() -> str:
    """Return a URL-safe, cryptographically secure device secret."""
    return secrets.token_urlsafe(48)


def hash_device_secret(raw_secret: str) -> str:
    """Return the hex HMAC-SHA256 of ``raw_secret`` keyed by the pepper."""
    key = _pepper().encode("utf-8")
    msg = (raw_secret or "").encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_device_secret(raw_secret: str, stored_hash: str) -> bool:
    """Constant-time comparison of a presented secret against the stored hash."""
    if not raw_secret or not stored_hash:
        return False
    computed = hash_device_secret(raw_secret)
    return hmac.compare_digest(computed, stored_hash)


def resolve_trusted_device(ctx) -> TrustedDevice | None:
    """Authenticate the device presented on the request.

    Returns ``None`` when NO device credentials were supplied (ordinary
    login). Raises ``ValidationFailed`` (generic message) when credentials
    were supplied but are invalid, inactive, or revoked — never silently
    falling back to normal login.

    On success updates ``last_used_at`` (flushed with the caller's commit).
    """
    client_id = (ctx.trusted_device_client_id or "").strip()
    secret = ctx.trusted_device_secret or ""

    if not client_id and not secret:
        return None

    if not client_id or not secret:
        raise ValidationFailed(_AUTH_FAILED_MESSAGE)

    device = (
        db.session.query(TrustedDevice)
        .filter(TrustedDevice.client_id == client_id)
        .first()
    )

    if device is None or not device.is_active or device.revoked_at is not None:
        raise ValidationFailed(_AUTH_FAILED_MESSAGE)

    if not verify_device_secret(secret, device.device_secret_hash):
        raise ValidationFailed(_AUTH_FAILED_MESSAGE)

    device.last_used_at = datetime.now(timezone.utc)
    return device


def is_user_assigned_to_device(user_id, trusted_device_id) -> bool:
    """True when an active assignment links this user to this device."""
    if user_id is None or trusted_device_id is None:
        return False
    return (
        db.session.query(TrustedDeviceUser)
        .filter(
            TrustedDeviceUser.trusted_device_id == trusted_device_id,
            TrustedDeviceUser.user_id == user_id,
            TrustedDeviceUser.is_active.is_(True),
        )
        .first()
        is not None
    )


def resolve_refresh_trusted_device(identity: dict) -> TrustedDevice | None:
    """Validate a refresh token's trusted-device context.

    Returns ``None`` for ordinary (single-user) refresh tokens. For
    trusted-device tokens, raises ``ValidationFailed`` when the device has
    been revoked/disabled or the user's assignment removed — this is what
    makes revocation effective within the access-token TTL given there is no
    JWT blocklist. On success returns the live device so its claims can be
    preserved on the refreshed token.
    """
    if identity.get("authentication_mode") != "trusted_device":
        return None

    device_id = identity.get("trusted_device_id")
    user_id = identity.get("user_id")

    device = db.session.get(TrustedDevice, device_id) if device_id is not None else None
    if device is None or not device.is_active or device.revoked_at is not None:
        raise ValidationFailed(_SESSION_INVALID_MESSAGE)

    if not is_user_assigned_to_device(user_id, device.id):
        raise ValidationFailed(_SESSION_INVALID_MESSAGE)

    return device
