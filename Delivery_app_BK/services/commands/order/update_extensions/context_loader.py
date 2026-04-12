from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from Delivery_app_BK.models import (
    InternationalShippingPlan,
    RouteGroup,
    RouteSolution,
    RouteSolutionStop,
    StorePickupPlan,
    db,
)
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_effective_order_plan_objective,
)

from ....context import ServiceContext
from .types import OrderUpdateDelta, OrderUpdateExtensionContext

PlanTypeContextLoader = Callable[
    [ServiceContext, list[int], list[OrderUpdateDelta], OrderUpdateExtensionContext],
    None,
]


def _resolve_plan_type(delta: OrderUpdateDelta) -> str | None:
    delivery_plan = delta.delivery_plan
    order = delta.order_instance
    return resolve_effective_order_plan_objective(
        getattr(order, "order_plan_objective", None),
        has_route_plan=delivery_plan is not None,
    )


def _collect_plan_ids_by_type(
    order_deltas: list[OrderUpdateDelta],
) -> dict[str, list[int]]:
    collected: defaultdict[str, set[int]] = defaultdict(set)
    for delta in order_deltas:
        delivery_plan = delta.delivery_plan
        plan_id = getattr(delivery_plan, "id", None)
        plan_type = _resolve_plan_type(delta)
        if plan_id is None or not plan_type:
            continue
        collected[plan_type].add(plan_id)

    return {
        plan_type: sorted(plan_ids)
        for plan_type, plan_ids in collected.items()
    }


def _load_local_delivery_context(
    ctx: ServiceContext,
    plan_ids: list[int],
    order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> None:
    local_context: dict[str, object] = {}

    route_group_query = db.session.query(RouteGroup).filter(
        RouteGroup.route_plan_id.in_(plan_ids)
    )
    if ctx.team_id:
        route_group_query = route_group_query.filter(RouteGroup.team_id == ctx.team_id)
    route_group_instances = route_group_query.all()
    route_group_by_plan_id = {
        instance.route_plan_id: instance for instance in route_group_instances
    }
    local_context["route_group_by_plan_id"] = route_group_by_plan_id

    route_group_ids = [instance.id for instance in route_group_instances]
    if not route_group_ids:
        extension_context.by_plan_type["local_delivery"] = local_context
        return

    route_query = db.session.query(RouteSolution).filter(
        RouteSolution.route_group_id.in_(route_group_ids)
    )
    if ctx.team_id:
        route_query = route_query.filter(RouteSolution.team_id == ctx.team_id)
    route_solutions = route_query.all()

    route_solutions_by_route_group_id: defaultdict[int, list[RouteSolution]] = defaultdict(
        list
    )
    route_solutions_by_id: dict[int, RouteSolution] = {}
    for route_solution in route_solutions:
        route_solutions_by_route_group_id[route_solution.route_group_id].append(
            route_solution
        )
        if route_solution.id is not None:
            route_solutions_by_id[route_solution.id] = route_solution

    route_solutions_by_route_group_id = dict(route_solutions_by_route_group_id)
    local_context["route_solutions_by_route_group_id"] = route_solutions_by_route_group_id
    local_context["route_solutions_by_id"] = route_solutions_by_id

    target_order_ids = sorted(
        {
            delta.order_instance.id
            for delta in order_deltas
            if getattr(delta.order_instance, "id", None) is not None
        }
    )
    route_solution_ids = list(route_solutions_by_id.keys())
    if not target_order_ids or not route_solution_ids:
        local_context["route_stops_by_order_id"] = {}
        extension_context.by_plan_type["local_delivery"] = local_context
        return

    stop_query = db.session.query(RouteSolutionStop).filter(
        RouteSolutionStop.order_id.in_(target_order_ids),
        RouteSolutionStop.route_solution_id.in_(route_solution_ids),
    )
    if ctx.team_id:
        stop_query = stop_query.filter(RouteSolutionStop.team_id == ctx.team_id)
    route_stops = stop_query.all()

    route_stops_by_order_id: defaultdict[int, list[RouteSolutionStop]] = defaultdict(list)
    for stop in route_stops:
        if stop.order_id is not None:
            route_stops_by_order_id[stop.order_id].append(stop)
    local_context["route_stops_by_order_id"] = dict(route_stops_by_order_id)
    extension_context.by_plan_type["local_delivery"] = local_context


def _load_international_shipping_context(
    ctx: ServiceContext,
    plan_ids: list[int],
    _order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> None:
    query = db.session.query(InternationalShippingPlan).filter(
        InternationalShippingPlan.route_plan_id.in_(plan_ids)
    )
    if ctx.team_id:
        query = query.filter(InternationalShippingPlan.team_id == ctx.team_id)
    extension_context.by_plan_type["international_shipping"] = {
        "international_shipping_by_plan_id": {
            instance.route_plan_id: instance for instance in query.all()
        }
    }


def _load_store_pickup_context(
    ctx: ServiceContext,
    plan_ids: list[int],
    _order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> None:
    query = db.session.query(StorePickupPlan).filter(
        StorePickupPlan.route_plan_id.in_(plan_ids)
    )
    if ctx.team_id:
        query = query.filter(StorePickupPlan.team_id == ctx.team_id)
    extension_context.by_plan_type["store_pickup"] = {
        "store_pickup_by_plan_id": {
            instance.route_plan_id: instance for instance in query.all()
        }
    }


PLAN_TYPE_CONTEXT_LOADERS: dict[str, PlanTypeContextLoader] = {
    "local_delivery": _load_local_delivery_context,
    "international_shipping": _load_international_shipping_context,
    "store_pickup": _load_store_pickup_context,
}


def build_order_update_extension_context(
    ctx: ServiceContext,
    order_deltas: list[OrderUpdateDelta],
) -> OrderUpdateExtensionContext:
    context = OrderUpdateExtensionContext()
    if not order_deltas:
        return context

    plan_ids_by_type = _collect_plan_ids_by_type(order_deltas)
    for plan_type, plan_ids in plan_ids_by_type.items():
        loader = PLAN_TYPE_CONTEXT_LOADERS.get(plan_type)
        if not loader:
            continue
        loader(ctx, plan_ids, order_deltas, context)
    return context
