from Delivery_app_BK.models import db, ItemProperty, ItemType, Item
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_item_property(ctx: ServiceContext):
    relationship_map = {
        "item_types": ItemType,
        "items": Item,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(ctx, ItemProperty, target["fields"], target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
