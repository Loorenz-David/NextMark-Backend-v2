from Delivery_app_BK.models import db, Vehicle
from ....context import ServiceContext
from ...base.delete_instance import delete_instance
from ...utils import extract_ids


def delete_vehicle(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, Vehicle, target_id))
    db.session.commit()
    return instances
