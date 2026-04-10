from Delivery_app_BK.models import UserRole
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_user_roles import serialize_user_roles


def get_user_role(role_id: int, ctx: ServiceContext):
    found_role = get_instance(
        ctx=ctx,
        model=UserRole,
        value=role_id,
    )

    if not found_role:
        raise NotFound(f"User role with id: {role_id} does not exist.")

    serialized = serialize_user_roles(
        instances=[found_role],
        ctx=ctx,
    )

    return {
        "user_role": serialized[0] if isinstance(serialized, list) else serialized
    }
