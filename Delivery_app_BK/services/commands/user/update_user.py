from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, User, UserRole
from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets


def update_user(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to update user profile.")

    allowed_fields = {
        "username",
        "email",
        "password",
        "phone_number",
        "profile_picture",
        "show_app_tutorial",
        "last_online",
        "last_location",
    }
    relationship_map = {
        "user_role_id": UserRole,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        fields = {
            key: value
            for key, value in target["fields"].items()
            if key in allowed_fields
        }
        if not fields:
            raise ValidationFailed("No allowed fields provided to update user profile.")

        if "password" in fields and fields["password"] is not None:
            fields["password"] = User().hash_password(fields["password"])

        instance: User = update_instance(ctx, User, fields, ctx.user_id)
        instances.append(instance.id)
    db.session.commit()
    return instances
