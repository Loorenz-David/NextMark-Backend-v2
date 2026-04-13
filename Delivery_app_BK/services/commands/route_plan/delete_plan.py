from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.models import db, RoutePlan
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from ...context import ServiceContext
from ..base.delete_instance import delete_instance
from ..utils import extract_ids


def delete_plan(ctx: ServiceContext):
    instances = []
    deleted_plans: list[dict] = []
    for target_id in extract_ids(ctx):
        plan = db.session.get(RoutePlan, target_id)
        if plan is not None:
            deleted_plans.append({
                "id": plan.id,
                "label": plan.label,
                "date_strategy": plan.date_strategy,
                "team_id": plan.team_id,
            })
        instances.append(delete_instance(ctx, RoutePlan, target_id))
    db.session.commit()

    for plan in deleted_plans:
        notify_delivery_planning_event(
            event_id=str(uuid4()),
            event_name="route_plan.deleted",
            team_id=plan["team_id"],
            entity_type="route_plan",
            entity_id=plan["id"],
            payload={
                "route_plan_id": plan["id"],
                "label": plan["label"],
                "plan_type": resolve_route_plan_workflow_type(),
                "date_strategy": plan["date_strategy"],
            },
            occurred_at=datetime.now(timezone.utc),
            actor=None,
        )
    return instances
