"""Local Delivery App - Order Objective Handler.

Handles creation of route solution stops when an order is assigned to a route plan.
"""

from __future__ import annotations

from collections.abc import Callable

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteGroup, RouteSolutionStop, db
from Delivery_app_BK.route_optimization.constants.skip_reasons import (
    ORDER_CREATED_AFTER_OPTIMIZATION,
)
from Delivery_app_BK.services.commands.order.create_serializers import (
    serialize_created_order_stops,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops import (
    build_route_solution_stops,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)
from ...context import ServiceContext
from ..order.plan_objectives.types import PlanObjectiveCreateResult


def apply_order_objective(
    ctx: ServiceContext,
    order_instance,
    route_plan,
    plan_objective: str,
) -> PlanObjectiveCreateResult:
    """Create route solution stops for an order assigned to a route plan.
    
    Args:
        ctx: Service context
        order_instance: Order being processed
        route_plan: RoutePlan instance
        plan_objective: Plan objective string
    
    Returns:
        PlanObjectiveCreateResult with created stops and side effects
    """
    local_delivery = _get_route_group(
        ctx,
        route_plan.id,
        getattr(order_instance, "route_group_id", None),
    )
    route_solutions = list(local_delivery.route_solutions or [])
    if not route_solutions:
        raise ValidationFailed("Route solution not found for local delivery plan.")
    synced_stops: list[RouteSolutionStop] = []
    changed_route_solutions: list[object] = []

    stop_instances, stop_links, updated_solutions = build_route_solution_stops(
        ctx,
        order_instance,
        route_solutions,
        skip_reason_for_optimized=_skip_reason_value(ORDER_CREATED_AFTER_OPTIMIZATION),
    )
    post_flush_actions = [
        _build_stop_order_link_action(stop_instance, order_instance)
        for stop_instance, order_instance in stop_links
    ]
    starts_by_route_id: dict[int, int] = {}
    for stop in stop_instances:
        route_id = (
            stop.route_solution_id
            or getattr(getattr(stop, "route_solution", None), "id", None)
        )
        if route_id is None:
            continue
        stop_order = stop.stop_order or 1
        current = starts_by_route_id.get(route_id)
        starts_by_route_id[route_id] = stop_order if current is None else min(current, stop_order)

    route_solutions_by_id = {
        route_solution.id: route_solution
        for route_solution in route_solutions
        if getattr(route_solution, "id", None) is not None
    }
    if starts_by_route_id:
        post_flush_actions.append(
            build_incremental_route_sync_action(
                ctx=ctx,
                starts_by_route_id=starts_by_route_id,
                route_solutions_by_id=route_solutions_by_id,
                synced_stops=synced_stops,
                changed_route_solutions=changed_route_solutions,
                orders_by_route_solution_resolver=lambda _route_solution, created_order=order_instance, plan=route_plan: _resolve_orders_for_incremental_sync(
                    plan,
                    created_order,
                ),
            )
        )

    return PlanObjectiveCreateResult(
        instances=stop_instances + updated_solutions,
        post_flush_actions=post_flush_actions,
        bundle_serializer=lambda created=stop_instances, synced=synced_stops, updated=updated_solutions, changed=changed_route_solutions: _serialize_bundle(
            _merge_changed_stops(created, synced),
            _merge_changed_route_solutions(updated, changed),
        ),
    )


def _get_route_group(
    ctx: ServiceContext,
    route_plan_id: int,
    route_group_id: int | None,
) -> RouteGroup:
    """Resolve route group for a plan, preferring explicit assignment when provided."""
    query = db.session.query(RouteGroup).filter(
        RouteGroup.route_plan_id == route_plan_id
    )
    if ctx.team_id:
        query = query.filter(RouteGroup.team_id == ctx.team_id)

    if route_group_id is not None:
        local_delivery = query.filter(RouteGroup.id == route_group_id).one_or_none()
        if not local_delivery:
            raise ValidationFailed("Route group not found for order objective.")
        return local_delivery

    route_groups = query.order_by(RouteGroup.id.asc()).all()
    if not route_groups:
        raise ValidationFailed("Route group not found for order objective.")
    if len(route_groups) > 1:
        raise ValidationFailed(
            "route_group_id is required when route plan has multiple route groups."
        )
    return route_groups[0]


def _skip_reason_value(reason) -> str | None:
    """Extract skip reason string from tuple or direct value."""
    if isinstance(reason, tuple):
        return reason[0] if reason else None
    return reason


def _resolve_orders_for_incremental_sync(
    delivery_plan,
    created_order,
) -> dict[int, object]:
    """Build orders dict for route sync action."""
    orders_by_id = {
        order.id: order
        for order in (delivery_plan.orders or [])
        if getattr(order, "id", None) is not None
    }
    created_order_id = getattr(created_order, "id", None)
    if created_order_id is not None:
        orders_by_id[created_order_id] = created_order
    return orders_by_id


def _build_stop_order_link_action(
    stop_instance: RouteSolutionStop,
    order_instance,
) -> Callable[[], None]:
    """Build post-flush action to link stop to order."""
    def _link() -> None:
        stop_instance.order_id = order_instance.id

    return _link


def _serialize_bundle(stops: list[RouteSolutionStop], route_solutions: list[object]) -> dict:
    """Serialize stops and route solutions for response."""
    bundle: dict = {}
    if stops:
        bundle["order_stops"] = serialize_created_order_stops(stops)
    if route_solutions:
        bundle["route_solution"] = [
            serialize_route_solution(route_solution)
            for route_solution in route_solutions
        ]
    return bundle


def _merge_changed_stops(
    created_stops: list[RouteSolutionStop],
    synced_stops: list[RouteSolutionStop],
) -> list[RouteSolutionStop]:
    """Merge and deduplicate created and synced stops."""
    merged = list(created_stops or []) + list(synced_stops or [])
    deduped: list[RouteSolutionStop] = []
    seen_ids: set[tuple[str, str]] = set()

    for stop in merged:
        stop_id = getattr(stop, "id", None)
        client_id = getattr(stop, "client_id", None)
        key = (
            "id" if stop_id is not None else "client_id",
            str(stop_id if stop_id is not None else client_id),
        )
        if key in seen_ids:
            continue
        seen_ids.add(key)
        deduped.append(stop)

    return sorted(
        deduped,
        key=lambda stop: (
            stop.stop_order if getattr(stop, "stop_order", None) is not None else 10**9,
            getattr(stop, "id", 10**9),
            getattr(stop, "client_id", ""),
        ),
    )


def _merge_changed_route_solutions(
    updated_solutions: list[object],
    changed_route_solutions: list[object],
) -> list[object]:
    """Merge and deduplicate updated and changed route solutions."""
    merged = list(updated_solutions or []) + list(changed_route_solutions or [])
    deduped: list[object] = []
    seen_ids: set[int] = set()

    for route_solution in merged:
        route_id = getattr(route_solution, "id", None)
        if route_id is None or route_id in seen_ids:
            continue
        seen_ids.add(route_id)
        deduped.append(route_solution)

    return deduped
