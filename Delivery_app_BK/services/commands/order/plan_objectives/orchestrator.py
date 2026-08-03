from __future__ import annotations

from collections.abc import Callable

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan, Order
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    normalize_order_plan_objective,
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

    # The plan owns the objective. Deriving it from the order instead let an order
    # be created as international shipping while sitting on a local delivery plan,
    # where the international handler is a no-op — so no stop was ever built and
    # the order was invisible to the route it belonged to.
    effective_objective = route_plan.plan_type

    requested_objective = normalize_order_plan_objective(
        order_instance.order_plan_objective
    ) or normalize_order_plan_objective(plan_objective)
    if requested_objective is not None and requested_objective != effective_objective:
        raise ValidationFailed(
            f"Order objective '{requested_objective}' does not match the "
            f"'{effective_objective}' plan it is being assigned to."
        )

    order_instance.order_plan_objective = effective_objective

    handler: PlanObjectiveHandler | None = PLAN_OBJECTIVE_HANDLERS.get(
        effective_objective
    )
    if not handler:
        return PlanObjectiveCreateResult()

    return handler(ctx, order_instance, route_plan, effective_objective)
