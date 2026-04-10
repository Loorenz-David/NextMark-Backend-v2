from typing import List
from ...context import ServiceContext
from Delivery_app_BK.models import db, Order
from ..utils import extract_ids


def unarchive_order(ctx: ServiceContext):

    target_ids = extract_ids(ctx)

    orders: List[Order] = (
        db.session.query(Order)
        .filter(Order.id.in_(target_ids))
        .all()
    )

    for order in orders:
        order.archive_at = None

    db.session.commit()
