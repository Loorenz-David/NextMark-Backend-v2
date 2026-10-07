from Delivery_app_BK.models import User, UserRole


def serialize_user_actor(instance: User, role: UserRole | None) -> dict:
    base_role = role.base_role if role else None
    return {
        "id": instance.id,
        "username": instance.username,
        "role_name": role.role_name if role else None,
        "base_role": ((base_role.role_name if base_role else "") or "").lower() or None,
    }
