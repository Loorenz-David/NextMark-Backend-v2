from Delivery_app_BK.models import db, ItemType
from ....context import ServiceContext
from ...base.delete_instance import delete_instance
from ...utils import extract_ids


def delete_item_type(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, ItemType, target_id))
    db.session.commit()
    return instances
