from typing import Dict, List

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import BaseRole, UserRole
from Delivery_app_BK.services.context import ServiceContext

from ..data import USER_ROLE_SEEDS
from ..helpers import ensure_client_id, get_or_create


def seed_user_roles(ctx: ServiceContext, base_roles: Dict[str, BaseRole]) -> List[UserRole]:
    if not base_roles:
        raise ValidationFailed("Missing base roles; run seed_base_roles first.")

    ctx.relationship_map = {
        **ctx.relationship_map,
         "base_role_id": BaseRole
    }

    user_roles: List[UserRole] = []

    for payload in USER_ROLE_SEEDS:
        base_role_key = payload.get("base_role_key")
        base_role = base_roles.get(base_role_key)
        if not base_role:
            raise ValidationFailed(f"Missing base role for key '{base_role_key}'.")

        fields = ensure_client_id(dict(payload))
        fields.pop("base_role_key", None)
        fields["base_role_id"] = base_role.id

        lookup = {
            "role_name": fields["role_name"],
            "base_role_id": base_role.id,
        }

        instance, _ = get_or_create(ctx, UserRole, lookup, fields)
        user_roles.append(instance)

    return user_roles
