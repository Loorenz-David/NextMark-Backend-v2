"""Local Delivery App - Order Update Extension Handler.

Handles route stop updates when order properties change (address, time window, etc).
"""

from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
)
from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)
from ...context import ServiceContext
from ..order.update_extensions.serializers import merge_bundle_payload
from ..order.update_extensions.types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


def apply_order_update_extension(
    ctx: ServiceContext,
    order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> OrderUpdateExtensionResult:
    """Apply route stop updates when order properties change.
    
    Args:
        ctx: Service context
        order_deltas: List of order change deltas
        extension_context: Pre-loaded context with route stops and solutions
    
    Returns:
        OrderUpdateExtensionResult with updated stops and side effects
    """
    result = OrderUpdateExtensionResult()
    if not order_deltas:
        return result

    starts_by_route_id: dict[int, int] = {}
    order_route_ids: dict[int, set[int]] = {}
    synced_stops: list[RouteSolutionStop] = []
    changed_route_solutions: list[RouteSolution] = []
    local_context = extension_context.by_plan_type.get("local_delivery", {})
    route_stops_by_order_id = local_context.get("route_stops_by_order_id", {})
    route_solutions_by_id = local_context.get("route_solutions_by_id", {})

    warning_changed_stops_by_order: defaultdict[int, list[RouteSolutionStop]] = defaultdict(
        list
    )

    for delta in order_deltas:
        order = delta.order_instance
        order_id = getattr(order, "id", None)
        if order_id is None:
            continue

        stops = list(route_stops_by_order_id.get(order_id) or [])
        if not stops:
            continue

        route_ids = {
            stop.route_solution_id
            for stop in stops
            if getattr(stop, "route_solution_id", None) is not None
        }
        if route_ids:
            order_route_ids[order_id] = route_ids

        if delta.flags.address_changed:
            for stop in stops:
                route_id = stop.route_solution_id
                if route_id is None:
                    continue
                stop_order = stop.stop_order or 1
                current = starts_by_route_id.get(route_id)
                starts_by_route_id[route_id] = (
                    stop_order if current is None else min(current, stop_order)
                )

        if delta.flags.window_changed and not delta.flags.address_changed:
            warning_changes = _apply_window_warning_updates(
                order,
                stops,
                route_solutions_by_id,
            )
            if warning_changes:
                warning_changed_stops_by_order[order_id].extend(warning_changes)

    for order_id, changed_stops in warning_changed_stops_by_order.items():
        merge_bundle_payload(
            result.bundle_by_order_id,
            order_id,
            stops=changed_stops,
        )
        result.instances.extend(changed_stops)

    if not starts_by_route_id:
        return result

    result.post_flush_actions.append(
        build_incremental_route_sync_action(
            ctx=ctx,
            starts_by_route_id=starts_by_route_id,
            route_solutions_by_id=route_solutions_by_id,
            synced_stops=synced_stops,
            changed_route_solutions=changed_route_solutions,
            orders_by_route_solution_resolver=_orders_by_route_solution,
        )
    )

    def _merge_synced_bundle() -> None:
        deduped_routes = _dedupe_routes(changed_route_solutions)
        for order_id, route_ids in order_route_ids.items():
            related_stops = [
                stop
                for stop in synced_stops
                if getattr(stop, "route_solution_id", None) in route_ids
            ]
            related_routes = [
                route
                for route in deduped_routes
                if getattr(route, "id", None) in route_ids
            ]
            merge_bundle_payload(
                result.bundle_by_order_id,
                order_id,
                stops=related_stops,
                route_solutions=related_routes,
            )

    result.post_flush_actions.append(_merge_synced_bundle)
    
    return result


def _orders_by_route_solution(route_solution: RouteSolution) -> dict[int, object]:
    """Extract orders from route solution's route plan."""
    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    return {
        order.id: order
        for order in ((route_plan.orders or []) if route_plan else [])
        if getattr(order, "id", None) is not None
    }


def _apply_window_warning_updates(
    order_instance,
    stops: list[RouteSolutionStop],
    route_solutions_by_id: dict[int, RouteSolution],
) -> list[RouteSolutionStop]:
    """Check if time window changes affect constraint violations."""
    changed: list[RouteSolutionStop] = []

    for stop in stops:
        route_solution = route_solutions_by_id.get(stop.route_solution_id)
        if not route_solution:
            continue

        previous_state = (
            stop.has_constraint_violation,
            stop.constraint_warnings,
            stop.reason_was_skipped,
        )
        apply_stop_time_window_evaluation(
            stop=stop,
            order=order_instance,
            route_solution=route_solution,
            arrival_time=stop.expected_arrival_time,
        )

        current_state = (
            stop.has_constraint_violation,
            stop.constraint_warnings,
            stop.reason_was_skipped,
        )
        if current_state != previous_state:
            changed.append(stop)

    return changed


def _dedupe_routes(route_solutions: list[RouteSolution]) -> list[RouteSolution]:
    """Deduplicate route solutions by id."""
    deduped: list[RouteSolution] = []
    seen_ids: set[int] = set()
    for route_solution in route_solutions or []:
        route_id = getattr(route_solution, "id", None)
        if route_id is None or route_id in seen_ids:
            continue
        seen_ids.add(route_id)
        deduped.append(route_solution)
    return deduped
