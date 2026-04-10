from __future__ import annotations

from Delivery_app_BK.directions.services.schedule_clamp import (
    apply_route_solution_schedule_clamp,
    group_contiguous_route_stops,
)
from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)

from ....context import ServiceContext
from .serializers import merge_bundle_payload
from .types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


def handle_local_delivery_order_update_extension(
    ctx: ServiceContext,
    order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> OrderUpdateExtensionResult:
    result = OrderUpdateExtensionResult()
    if not order_deltas:
        return result

    starts_by_route_id: dict[int, int] = {}
    clamp_starts_by_route_id: dict[int, int] = {}
    order_route_ids: dict[int, set[int]] = {}
    synced_stops: list[RouteSolutionStop] = []
    clamped_stops: list[RouteSolutionStop] = []
    changed_route_solutions: list[RouteSolution] = []
    clamped_route_solutions: list[RouteSolution] = []
    local_context = extension_context.by_plan_type.get("local_delivery", {})
    route_stops_by_order_id = local_context.get("route_stops_by_order_id", {})
    route_solutions_by_id = local_context.get("route_solutions_by_id", {})

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
            for stop in stops:
                route_id = stop.route_solution_id
                if route_id is None:
                    continue
                stop_order = stop.stop_order or 1
                current = clamp_starts_by_route_id.get(route_id)
                clamp_starts_by_route_id[route_id] = (
                    stop_order if current is None else min(current, stop_order)
                )

    if not starts_by_route_id:
        pass
    else:
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

    if clamp_starts_by_route_id:
        result.post_flush_actions.append(
            _build_window_clamp_action(
                starts_by_route_id=clamp_starts_by_route_id,
                route_solutions_by_id=route_solutions_by_id,
                clamped_stops=clamped_stops,
                clamped_route_solutions=clamped_route_solutions,
                orders_by_route_solution_resolver=_orders_by_route_solution,
            )
        )

    if not starts_by_route_id and not clamp_starts_by_route_id:
        return result

    def _merge_synced_bundle() -> None:
        deduped_routes = _dedupe_routes([*changed_route_solutions, *clamped_route_solutions])
        result.instances.extend(synced_stops)
        result.instances.extend(clamped_stops)
        result.instances.extend(deduped_routes)

        all_changed_stops = [*synced_stops, *clamped_stops]
        for order_id, route_ids in order_route_ids.items():
            related_stops = [
                stop
                for stop in all_changed_stops
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


def _build_window_clamp_action(
    *,
    starts_by_route_id: dict[int, int],
    route_solutions_by_id: dict[int, RouteSolution],
    clamped_stops: list[RouteSolutionStop],
    clamped_route_solutions: list[RouteSolution],
    orders_by_route_solution_resolver,
):
    def _clamp() -> None:
        for route_id, start_position in starts_by_route_id.items():
            route_solution = route_solutions_by_id.get(route_id)
            if route_solution is None:
                continue

            orders_by_id = orders_by_route_solution_resolver(route_solution)
            ordered_suffix = [
                stop
                for stop in sorted(
                    [stop for stop in (route_solution.stops or []) if stop.order_id],
                    key=lambda stop: stop.stop_order if stop.stop_order is not None else 0,
                )
                if (stop.stop_order or 0) >= max(1, int(start_position or 1))
            ]
            grouped_stops = group_contiguous_route_stops(ordered_suffix, orders_by_id)
            changed_stops, route_changed = apply_route_solution_schedule_clamp(
                route_solution=route_solution,
                grouped_stops=grouped_stops,
                orders_by_id=orders_by_id,
                base_end_time=route_solution.expected_end_time,
            )
            clamped_stops.extend(changed_stops or [])
            if route_changed:
                clamped_route_solutions.append(route_solution)

    return _clamp


def _orders_by_route_solution(route_solution: RouteSolution) -> dict[int, object]:
    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    return {
        order.id: order
        for order in ((route_plan.orders or []) if route_plan else [])
        if getattr(order, "id", None) is not None
    }


def _dedupe_routes(route_solutions: list[RouteSolution]) -> list[RouteSolution]:
    deduped: list[RouteSolution] = []
    seen_ids: set[int] = set()
    for route_solution in route_solutions or []:
        route_id = getattr(route_solution, "id", None)
        if route_id is None or route_id in seen_ids:
            continue
        seen_ids.add(route_id)
        deduped.append(route_solution)
    return deduped
