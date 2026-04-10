from Delivery_app_BK.models import db, ItemType, ItemProperty, Team
from ....context import ServiceContext
from ...base.create_instance import create_instance
from ...utils import extract_fields, build_create_result


def create_item_type(ctx: ServiceContext):
    relationship_map = {
        "properties": ItemProperty,
        "team_id": Team

    }

    ctx.set_relationship_map(relationship_map)
    instances = []

    for field_set in extract_fields(ctx):
       
        instance = create_instance(ctx, ItemType, dict(field_set))
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
