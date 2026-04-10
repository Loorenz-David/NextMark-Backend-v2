from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.services.commands.order.update_extensions.serializers import (
    merge_bundle_payload,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops import (
    remove_orders_stops_for_local_delivery,
)

from ....context import ServiceContext
from .types import OrderDeleteDelta, OrderDeleteExtensionContext, OrderDeleteExtensionResult


def handle_local_delivery_order_delete_extension(
    ctx: ServiceContext,
    delete_deltas: list[OrderDeleteDelta],
    extension_context: OrderDeleteExtensionContext,
) -> OrderDeleteExtensionResult:
    result = OrderDeleteExtensionResult()
    if not delete_deltas:
        return result

    local_context = extension_context.by_plan_type.get("local_delivery", {})
    route_group_by_plan_id = local_context.get("route_group_by_plan_id", {})
    route_solutions_by_id = local_context.get("route_solutions_by_id", {})

    grouped_order_ids_by_local_delivery_id: defaultdict[int, list[int]] = defaultdict(list)
    for delta in delete_deltas:
        delivery_plan = delta.delivery_plan
        if not delivery_plan:
            continue
        local_delivery = route_group_by_plan_id.get(delivery_plan.id)
        if not local_delivery:
            continue
        grouped_order_ids_by_local_delivery_id[local_delivery.id].append(delta.order_id)

    if not grouped_order_ids_by_local_delivery_id:
        return result

    starts_by_route_id: dict[int, int] = {}
    synced_stops: list[RouteSolutionStop] = []
    changed_route_solutions: list[RouteSolution] = []
    touched_route_ids: set[int] = set()
    touched_routes: list[RouteSolution] = []

    for local_delivery_id, order_ids in grouped_order_ids_by_local_delivery_id.items():
        deduped_order_ids = list(dict.fromkeys(order_ids))
        (
            updated_stops,
            updated_route_solutions,
            affected_start_by_route,
        ) = remove_orders_stops_for_local_delivery(deduped_order_ids, local_delivery_id)

        result.instances.extend(updated_stops)
        result.instances.extend(updated_route_solutions)
        touched_routes.extend(updated_route_solutions)

        for route_id, start_position in affected_start_by_route.items():
            if route_id is None:
                continue
            touched_route_ids.add(route_id)
            current = starts_by_route_id.get(route_id)
            starts_by_route_id[route_id] = (
                start_position if current is None else min(current, start_position)
            )

    for route_solution in touched_routes:
        route_id = getattr(route_solution, "id", None)
        if route_id is not None:
            touched_route_ids.add(route_id)
            route_solutions_by_id[route_id] = route_solution

    if starts_by_route_id:
        result.post_flush_actions.append(
            build_incremental_route_sync_action(
                ctx=ctx,
                starts_by_route_id=starts_by_route_id,
                route_solutions_by_id=route_solutions_by_id,
                synced_stops=synced_stops,
                changed_route_solutions=changed_route_solutions,
            )
        )

    def _merge_updated_bundle() -> None:
        if not touched_route_ids:
            return

        bundle_by_route_id: dict[int, dict] = {}
        touched_routes_by_id = {
            route.id: route
            for route in _dedupe_routes(touched_routes + changed_route_solutions)
            if getattr(route, "id", None) is not None
        }
        for route_id in touched_route_ids:
            route = touched_routes_by_id.get(route_id)
            if route:
                merge_bundle_payload(
                    bundle_by_route_id,
                    route_id,
                    route_solutions=[route],
                )

        for stop in synced_stops:
            route_id = getattr(stop, "route_solution_id", None)
            if route_id is None:
                continue
            merge_bundle_payload(
                bundle_by_route_id,
                route_id,
                stops=[stop],
            )

        result.updated_bundles.extend(bundle_by_route_id.values())

    result.post_flush_actions.append(_merge_updated_bundle)
    return result


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
