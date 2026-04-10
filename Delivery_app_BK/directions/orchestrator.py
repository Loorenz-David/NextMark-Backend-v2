from __future__ import annotations

from typing import Dict

from Delivery_app_BK.directions.providers.base import DirectionsProvider
from Delivery_app_BK.directions.providers.google import GoogleDirectionsProvider
from Delivery_app_BK.directions.services.refresher import apply_directions_result
from Delivery_app_BK.directions.services.request_builder import (
    build_directions_request_bundle,
)
from Delivery_app_BK.models import Order, RouteSolution, RouteSolutionStop


def refresh_route_solution(
    route_solution: RouteSolution,
    provider: DirectionsProvider | None = None,
    time_zone: str | None = None,
    orders_by_id: Dict[int, Order] | None = None,
    recompute_from_position: int = 1,
) -> RouteSolution:
    refresh_route_solution_incremental(
        route_solution=route_solution,
        provider=provider,
        time_zone=time_zone,
        orders_by_id=orders_by_id,
        recompute_from_position=recompute_from_position,
    )
    return route_solution


def refresh_route_solution_incremental(
    route_solution: RouteSolution,
    provider: DirectionsProvider | None = None,
    time_zone: str | None = None,
    orders_by_id: Dict[int, Order] | None = None,
    recompute_from_position: int = 1,
) -> list[RouteSolutionStop]:
  
    resolved_orders = _resolve_orders_by_id(route_solution, orders_by_id)
    build_result = build_directions_request_bundle(
        route_solution=route_solution,
        orders_by_id=resolved_orders,
        time_zone=time_zone,
        recompute_from_position=recompute_from_position,
    )

    provider = provider or GoogleDirectionsProvider()
   
    result = provider.compute(build_result.request)
   
   
    return apply_directions_result(
        route_solution=route_solution,
        directions_result=result,
        orders_by_id=resolved_orders,
        build_result=build_result,
    )


def _resolve_orders_by_id(
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order] | None,
) -> Dict[int, Order]:
    if orders_by_id is not None:
        return orders_by_id

    resolved: Dict[int, Order] = {}
    route_plan = None
    if route_solution.route_group:
        route_plan = route_solution.route_group.route_plan

    for order in (route_plan.orders if route_plan else []) or []:
        if order.id is not None:
            resolved[order.id] = order

    if resolved:
        return resolved

    for stop in (route_solution.stops or []) or []:
        order = getattr(stop, "order", None)
        if order and order.id is not None:
            resolved[order.id] = order

    return resolved
