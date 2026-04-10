from Delivery_app_BK.models import db, ItemType, ItemProperty
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_item_type(ctx: ServiceContext):
    relationship_map = {
        "properties": ItemProperty,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(ctx, ItemType, target["fields"], target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
