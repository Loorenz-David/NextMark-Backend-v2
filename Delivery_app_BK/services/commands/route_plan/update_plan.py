from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.models import db, Order, RoutePlan, Team, RoutePlanState
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.infra.events.builders.order import build_delivery_rescheduled_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.requests.common.datetime import validate_time_range
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery.update_settings import (
    RoutePlanPatchRequest,
)

from ...context import ServiceContext
from ..base.update_instance import update_instance
from ..utils import extract_targets


def _derive_date_strategy_from_dates(
    start_date: datetime | None,
    end_date: datetime | None,
) -> str | None:
    if start_date is None or end_date is None:
        return None

    if start_date.date() == end_date.date():
        return "single"

    return "range"


def apply_route_plan_patch(
    route_plan: RoutePlan,
    patch: RoutePlanPatchRequest,
) -> tuple[datetime | None, datetime | None, list[dict]]:
    previous_start = route_plan.start_date
    previous_end = route_plan.end_date

    if patch.has_label:
        route_plan.label = patch.label

    if patch.has_start_date and patch.start_date is not None:
        route_plan.start_date = patch.start_date

    if patch.has_end_date and patch.end_date is not None:
        route_plan.end_date = patch.end_date

    derived_date_strategy = _derive_date_strategy_from_dates(
        route_plan.start_date,
        route_plan.end_date,
    )
    if derived_date_strategy is not None:
        route_plan.date_strategy = derived_date_strategy

    validate_time_range(
        route_plan.start_date,
        route_plan.end_date,
        label="route plan",
    )

    return previous_start, previous_end, []


def apply_delivery_plan_patch(
    route_plan: RoutePlan,
    patch: RoutePlanPatchRequest,
) -> tuple[datetime | None, datetime | None, list[dict]]:
    # Backward-compatible alias while route_plan naming is rolled out.
    return apply_route_plan_patch(route_plan, patch)


def update_plan(ctx: ServiceContext):
    ctx.set_relationship_map(
        {
            "team_id": Team,
            "state_id": RoutePlanState,
        }
    )

    updated_plans: list[RoutePlan] = []
    updated_ids: list[int] = []
    pending_order_events: list[dict] = []

    for target in extract_targets(ctx):
        fields = dict(target["fields"] or {})
        # Legacy plan-type fields are no longer supported under RoutePlan.
        fields.pop("plan_type", None)
        fields.pop("local_delivery", None)
        fields.pop("international_shipping", None)
        fields.pop("store_pickup", None)

        previous_instance = db.session.get(RoutePlan, target["target_id"])
        previous_start = getattr(previous_instance, "start_date", None)
        previous_end = getattr(previous_instance, "end_date", None)

        instance: RoutePlan = update_instance(ctx, RoutePlan, fields, target["target_id"])
        touch_route_freshness(instance)

        if (previous_start, previous_end) != (instance.start_date, instance.end_date):
            plan_orders = (
                db.session.query(Order)
                .filter(Order.route_plan_id == instance.id)
                .filter(Order.team_id == ctx.team_id)
                .all()
            )
            for order in plan_orders:
                pending_order_events.append(
                    build_delivery_rescheduled_event(
                        order,
                        old_plan_start=previous_start,
                        old_plan_end=previous_end,
                        new_plan_start=instance.start_date,
                        new_plan_end=instance.end_date,
                        reason="plan_window_changed",
                    )
                )

        updated_plans.append(instance)
        updated_ids.append(instance.id)

    db.session.commit()

    if pending_order_events:
        emit_order_events(ctx, pending_order_events)

    for instance in updated_plans:
        notify_delivery_planning_event(
            event_id=str(uuid4()),
            event_name="route_plan.updated",
            team_id=instance.team_id,
            entity_type="route_plan",
            entity_id=instance.id,
            payload={
                "route_plan_id": instance.id,
                "label": instance.label,
                "plan_type": resolve_route_plan_workflow_type(),
                "date_strategy": instance.date_strategy,
                "route_freshness_updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
            },
            occurred_at=instance.updated_at or datetime.now(timezone.utc),
            actor=None,
        )
    return updated_ids
