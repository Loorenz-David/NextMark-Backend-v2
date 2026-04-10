from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, ItemState
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_item_state(ctx: ServiceContext):
    instances = []
    allowed_fields = {
        "client_id",
        "name",
        "color",
        "default",
        "description",
        "index",
    }
    for target in extract_targets(ctx):
        fields = {
            key: value
            for key, value in target["fields"].items()
            if key in allowed_fields
        }
        if not fields:
            raise ValidationFailed("No allowed fields provided to update item state.")
        instance = update_instance(ctx, ItemState, fields, target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
