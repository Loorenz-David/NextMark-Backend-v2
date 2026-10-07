"""Order retention background job tasks.

purge_unplanned_orders_job — run periodically by the scheduler; deletes
orders kept without an objective once their discard_after has passed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from Delivery_app_BK.services.infra.jobs import with_app_context

logger = logging.getLogger(__name__)

PURGE_BATCH_SIZE = 500


@with_app_context
def purge_unplanned_orders_job() -> int:
    from Delivery_app_BK.models import db
    from Delivery_app_BK.services.commands.order.delete_order import delete_order
    from Delivery_app_BK.services.context import ServiceContext
    from Delivery_app_BK.services.queries.order.find_discardable_unplanned_orders import (
        find_discardable_unplanned_orders,
    )

    order_ids_by_team = find_discardable_unplanned_orders(
        now=datetime.now(timezone.utc),
        limit=PURGE_BATCH_SIZE,
    )

    purged = 0
    for team_id, order_ids in order_ids_by_team.items():
        ctx = ServiceContext(
            incoming_data={"target_ids": order_ids},
            identity={"team_id": team_id, "active_team_id": team_id},
        )
        try:
            delete_order(ctx)
        except Exception:
            db.session.rollback()
            logger.exception(
                "Unplanned order purge failed | team_id=%s order_ids=%s",
                team_id,
                order_ids,
            )
            continue
        purged += len(order_ids)
        logger.info(
            "Unplanned orders purged | team_id=%s count=%s",
            team_id,
            len(order_ids),
        )

    return purged
