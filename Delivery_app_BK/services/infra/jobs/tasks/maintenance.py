from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import or_

from Delivery_app_BK.models import RoutePlanEventAction, OrderEventAction, db
from Delivery_app_BK.services.infra.events.action_dispatch import (
    enqueue_route_plan_action,
    enqueue_order_action,
)
from Delivery_app_BK.services.infra.events.dispatcher import repair_stale_claims
from Delivery_app_BK.services.infra.jobs import with_app_context


@with_app_context
def repair_stale_dispatch_claims_job() -> int:
    from flask import current_app

    repaired = repair_stale_claims(
        lease_seconds=current_app.config.get("REDIS_DISPATCHER_LEASE_SECONDS", 120),
    )
    if repaired:
        db.session.commit()
    return repaired


@with_app_context
def requeue_stale_message_actions_job() -> int:
    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    requeued = 0

    order_actions = (
        db.session.query(OrderEventAction)
        .filter(
            OrderEventAction.status == OrderEventAction.STATUS_PENDING,
            OrderEventAction.enqueued_at.isnot(None),
            or_(
                OrderEventAction.scheduled_for.is_(None),
                OrderEventAction.scheduled_for <= datetime.now(timezone.utc),
            ),
            OrderEventAction.updated_at < threshold,
        )
        .all()
    )
    for action in order_actions:
        enqueue_order_action(action)
        requeued += 1

    plan_actions = (
        db.session.query(RoutePlanEventAction)
        .filter(
            RoutePlanEventAction.status == RoutePlanEventAction.STATUS_PENDING,
            RoutePlanEventAction.enqueued_at.isnot(None),
            or_(
                RoutePlanEventAction.scheduled_for.is_(None),
                RoutePlanEventAction.scheduled_for <= datetime.now(timezone.utc),
            ),
            RoutePlanEventAction.updated_at < threshold,
        )
        .all()
    )
    for action in plan_actions:
        enqueue_route_plan_action(action)
        requeued += 1

    return requeued
