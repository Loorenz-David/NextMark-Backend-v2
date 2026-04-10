from Delivery_app_BK.models import db, ItemProperty, ItemType, Item, Team
from ....context import ServiceContext
from ...base.create_instance import create_instance
from ...utils import extract_fields, build_create_result


def create_item_property(ctx: ServiceContext):
    relationship_map = {
        "item_types": ItemType,
        "items": Item,
        "team_id":Team
    }
    ctx.set_relationship_map(relationship_map)
    instances = []

    for field_set in extract_fields(ctx):
        instance = create_instance(ctx, ItemProperty, dict(field_set))
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
