from __future__ import annotations

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan, Order
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    normalize_order_plan_objective,
)
from Delivery_app_BK.services.plan_types.registry import get_plan_type_module
from Delivery_app_BK.services.queries.get_instance import get_instance

from ....context import ServiceContext
from .types import PlanObjectiveCreateResult


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

    plan_type_module = get_plan_type_module(effective_objective)
    if plan_type_module is None:
        return PlanObjectiveCreateResult()

    return plan_type_module.apply_objective(
        ctx, order_instance, route_plan, effective_objective
    )
