from __future__ import annotations

from collections.abc import Callable

from Delivery_app_BK.models import RoutePlan, Order
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_effective_order_plan_objective,
)
from Delivery_app_BK.services.queries.get_instance import get_instance

from ....context import ServiceContext
from ...local_delivery_app import apply_order_objective as apply_local_delivery_objective
from ...store_pickup_app import apply_order_objective as apply_store_pickup_objective
from ...international_shipping_app import apply_order_objective as apply_international_shipping_objective
from .types import PlanObjectiveCreateResult


PlanObjectiveHandler = Callable[
    [ServiceContext, Order, RoutePlan, str],
    PlanObjectiveCreateResult,
]


PLAN_OBJECTIVE_HANDLERS = {
    "local_delivery": apply_local_delivery_objective,
    "store_pickup": apply_store_pickup_objective,
    "international_shipping": apply_international_shipping_objective,
}


def apply_order_plan_objective(
    ctx: ServiceContext,
    order_instance: Order,
    route_plan_id: int | None = None,
    plan_objective: str | None = None,
    route_plan: RoutePlan | None = None,
) -> PlanObjectiveCreateResult:
    if not route_plan and not route_plan_id:
        return PlanObjectiveCreateResult()

    if route_plan is None:
        route_plan = get_instance(
            ctx=ctx,
            model=RoutePlan,
            value=route_plan_id,
        )

    effective_objective = resolve_effective_order_plan_objective(
        order_instance.order_plan_objective,
        has_route_plan=route_plan is not None,
        fallback=plan_objective,
    )
    if not order_instance.order_plan_objective:
        order_instance.order_plan_objective = effective_objective

    handler: PlanObjectiveHandler | None = PLAN_OBJECTIVE_HANDLERS.get(
        effective_objective
    )
    if not handler:
        return PlanObjectiveCreateResult()

    return handler(ctx, order_instance, route_plan, effective_objective)
