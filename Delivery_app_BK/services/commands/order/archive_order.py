from typing import List
from ...context import ServiceContext
from datetime import datetime, timezone
from Delivery_app_BK.models import (
    db,
    Order,
)
from ..utils import extract_ids


def archive_order(ctx:ServiceContext):

    target_ids = extract_ids(ctx)
   
    orders:List[Order] = db.session.query(Order).filter(Order.id.in_(target_ids)).all()
    for order in orders:
        order.archive_at = datetime.now(timezone.utc)
    
    db.session.commit()

