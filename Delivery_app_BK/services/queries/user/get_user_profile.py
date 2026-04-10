from Delivery_app_BK.models import User
from Delivery_app_BK.errors import NotFound, ValidationFailed

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_user import serialize_user


def get_user_profile(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to fetch the profile.")

    found_user = get_instance(
        ctx=ctx,
        model=User,
        value=ctx.user_id,
    )

    if not found_user:
        raise NotFound(f"User with id: {ctx.user_id} does not exist.")

    serialized = serialize_user(
        instance=found_user,
        ctx=ctx,
    )

    return {
        "user": serialized[0] if isinstance(serialized, list) else serialized
    }
