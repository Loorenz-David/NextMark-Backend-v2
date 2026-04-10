from __future__ import annotations

from typing import Iterable, List, Tuple

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_OPTIMIZE, IS_OPTIMIZED_PARTIAL
)
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    get_next_route_stop_order,
    lock_route_solution,
)

from Delivery_app_BK.services.context import ServiceContext


def build_route_solution_stops_for_order_ids(
    ctx: ServiceContext,
    order_ids: Iterable[int | None],
    route_solutions: List[RouteSolution],
    skip_reason_for_optimized: str | None = None,
) -> Tuple[List[RouteSolutionStop], List[RouteSolution]]:
    stop_instances: List[RouteSolutionStop] = []
    updated_route_solutions: List[RouteSolution] = []
    order_id_list = list(order_ids)

    for route_solution in route_solutions:
        if getattr(route_solution, "id", None) is not None:
            lock_route_solution(route_solution.id)

        current_stop = _resolve_current_stop_order(route_solution)
        for order_id in order_id_list:
            current_stop += 1
            stop_instance = RouteSolutionStop(
                client_id=generate_client_id('route_stop'),
                stop_order=current_stop,
                team_id=ctx.team_id,
            )
            stop_instance.route_solution = route_solution
            if order_id is not None:
                stop_instance.order_id = order_id

            if ( route_solution.is_optimized == IS_OPTIMIZED_OPTIMIZE or route_solution.is_optimized == IS_OPTIMIZED_PARTIAL)  and skip_reason_for_optimized:
                stop_instance.in_range = False
                stop_instance.reason_was_skipped = _skip_reason_value(
                    skip_reason_for_optimized
                )

            stop_instances.append(stop_instance)

        updated_route_solutions.append(route_solution)

    return stop_instances, updated_route_solutions


def build_route_solution_stops(
    ctx: ServiceContext,
    order_instance,
    route_solutions: List[RouteSolution],
    skip_reason_for_optimized: str | None = None,
) -> Tuple[List[RouteSolutionStop], List[Tuple[RouteSolutionStop, object]], List[RouteSolution]]:
    stop_instances, updated_route_solutions = build_route_solution_stops_for_order_ids(
        ctx,
        [None],
        route_solutions,
        skip_reason_for_optimized=skip_reason_for_optimized,
    )
    stop_links: List[Tuple[RouteSolutionStop, object]] = [
        (stop_instance, order_instance) for stop_instance in stop_instances
    ]
    return stop_instances, stop_links, updated_route_solutions


def _skip_reason_value(reason) -> str | None:
    if isinstance(reason, tuple):
        return reason[0] if reason else None
    return reason


def _resolve_current_stop_order(route_solution: RouteSolution) -> int:
    """Return the current max stop order for a route, including pending in-memory stops.

    This avoids duplicate stop_order values when multiple stops are created in the
    same session before a flush/commit.
    """
    in_memory_max = max(
        (
            int(stop.stop_order)
            for stop in (route_solution.stops or [])
            if getattr(stop, "stop_order", None) is not None
        ),
        default=0,
    )
    db_max = get_next_route_stop_order(getattr(route_solution, "id", None)) - 1
    return max(in_memory_max, db_max)
