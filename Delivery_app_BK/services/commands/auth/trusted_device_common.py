"""Shared lookups and serializers for trusted-device management.

All lookups are scoped to the caller's team (``ctx.team_id``) so one team's
admins can never read or mutate another team's devices or assignments.
"""

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db, TrustedDevice, TrustedDeviceUser, User


def load_team_device(ctx, device_client_id: str) -> TrustedDevice:
    if not device_client_id:
        raise ValidationFailed("device_client_id is required.")
    device = (
        db.session.query(TrustedDevice)
        .filter(
            TrustedDevice.client_id == device_client_id,
            TrustedDevice.team_id == ctx.team_id,
        )
        .first()
    )
    if device is None:
        raise NotFound("Trusted device was not found.")
    return device


def load_team_user_by_client_id(ctx, user_client_id: str) -> User:
    if not user_client_id:
        raise ValidationFailed("user_client_id is required.")
    user = (
        db.session.query(User)
        .filter(
            User.client_id == user_client_id,
            User.team_id == ctx.team_id,
        )
        .first()
    )
    if user is None:
        raise NotFound("User was not found in this team.")
    return user


def serialize_device(device: TrustedDevice) -> dict:
    return {
        "client_id": device.client_id,
        "name": device.name,
        "is_active": device.is_active,
        "last_used_at": device.last_used_at.isoformat() if device.last_used_at else None,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
    }


def serialize_assigned_user(user: User) -> dict:
    return {
        "id": user.id,
        "client_id": user.client_id,
        "username": user.username,
        "profile_picture": user.profile_picture,
    }


def load_active_assigned_users(device_id: int) -> list[User]:
    """All users with an active assignment to the device (single query)."""
    from sqlalchemy.orm import joinedload

    assignments = (
        db.session.query(TrustedDeviceUser)
        .filter(
            TrustedDeviceUser.trusted_device_id == device_id,
            TrustedDeviceUser.is_active.is_(True),
        )
        .options(joinedload(TrustedDeviceUser.user))
        .all()
    )
    users = [a.user for a in assignments if a.user is not None]
    users.sort(key=lambda u: (u.username or "").lower())
    return users
