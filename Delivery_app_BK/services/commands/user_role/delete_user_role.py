from Delivery_app_BK.models import db, UserRole
from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext
from ..base.delete_instance import delete_instance
from ..utils import extract_ids
from ...queries.get_instance import get_instance


def delete_user_role(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        role:UserRole = get_instance(ctx=ctx, model=UserRole, value=target_id)
        if role.is_system and not ctx.allow_is_system_modification:
            raise ValidationFailed("System roles cannot be deleted.")
        instances.append(delete_instance(ctx, UserRole, target_id))
    db.session.commit()
    return instances
