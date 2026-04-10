from Delivery_app_BK.models import db, DateRangeAccessRule

from ....context import ServiceContext
from ...base.delete_instance import delete_instance
from ...utils import extract_ids


def delete_date_range_access_rule(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, DateRangeAccessRule, target_id))
    db.session.commit()
    return instances
