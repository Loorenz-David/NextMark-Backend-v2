from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, ItemState, Team
from ....context import ServiceContext
from ...base.create_instance import create_instance
from ...utils import extract_fields, build_create_result


def create_item_state(ctx: ServiceContext):
    relationship_map = {
        "team_id":Team
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    allowed_fields = {
        "client_id",
        "name",
        "color",
        "default",
        "description",
        "index",
    }

    for field_set in extract_fields(ctx):
        fields = {key: value for key, value in field_set.items() if key in allowed_fields}
        if not fields:
            raise ValidationFailed("No allowed fields provided to create item state.")
        instance = create_instance(ctx, ItemState, fields)
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
