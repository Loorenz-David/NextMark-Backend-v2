"""International Shipping App - plan creation.

Deliberately does not reuse the route-operations create command: that one always
builds a no-zone route group and a route solution, which are route-operations
artifacts an international shipping plan has no use for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.models import (
    InternationalShippingPlan,
    Order,
    RoutePlan,
    RoutePlanState,
    Team,
    User,
    db,
)
from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    apply_orders_route_plan_change,
)
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.requests.route_plan.international_shipping.create_plan import (
    parse_create_international_shipping_plan_request,
)
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event

from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields
from .create_serializers import serialize_created_international_shipping_bundle


PLAN_TYPE = "international_shipping"


def create_international_shipping_plan(ctx: ServiceContext) -> dict:
    ctx.set_relationship_map(
        {
            "team_id": Team,
            "state_id": RoutePlanState,
            "orders": Order,
        }
    )

    create_items = [
        parse_create_international_shipping_plan_request(field_set)
        for field_set in extract_fields(ctx)
    ]

    created_bundles: list[dict] = []
    pending_order_events: list[dict] = []

    def _apply() -> None:
        for item in create_items:
            shell = item.shell

            route_plan: RoutePlan = create_instance(
                ctx,
                RoutePlan,
                {
                    "client_id": shell.client_id,
                    "label": shell.label,
                    "plan_type": PLAN_TYPE,
                    "date_strategy": shell.date_strategy,
                    "start_date": shell.start_date,
                    "end_date": shell.end_date,
                    "state_id": PlanStateId.OPEN,
                },
            )
            db.session.add(route_plan)
            # The child's route_plan_id is non-nullable, so the parent id has to
            # exist before it can be built.
            db.session.flush()

            shipping_plan: InternationalShippingPlan = create_instance(
                ctx,
                InternationalShippingPlan,
                {
                    "route_plan_id": route_plan.id,
                    "carrier_name": item.carrier_name,
                },
            )
            db.session.add(shipping_plan)
            db.session.flush()

            if shell.order_ids:
                # Adopts the plan's type on each order and tears down whatever the
                # order's previous domain had built for it.
                outcome = apply_orders_route_plan_change(
                    ctx,
                    shell.order_ids,
                    route_plan.id,
                )
                pending_order_events.extend(outcome["pending_events"])

            created_bundles.append(
                serialize_created_international_shipping_bundle(route_plan, shipping_plan)
            )

    with db.session.begin():
        _apply()

    if pending_order_events:
        emit_order_events(ctx, pending_order_events)

    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
    for bundle in created_bundles:
        route_plan_payload = bundle["route_plan"]
        notify_delivery_planning_event(
            event_id=str(uuid4()),
            event_name="route_plan.created",
            team_id=ctx.team_id,
            entity_type="route_plan",
            entity_id=route_plan_payload["id"],
            payload={
                "route_plan_id": route_plan_payload["id"],
                "label": route_plan_payload["label"],
                "plan_type": route_plan_payload["plan_type"],
                "date_strategy": route_plan_payload["date_strategy"],
            },
            occurred_at=datetime.now(timezone.utc),
            actor=actor,
        )

    return {"created": created_bundles}
