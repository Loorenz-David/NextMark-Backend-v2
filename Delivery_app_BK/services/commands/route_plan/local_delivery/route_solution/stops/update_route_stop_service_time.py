from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.directions import refresh_route_solution_incremental
from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, User, db
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_OPTIMIZE,
    IS_OPTIMIZED_PARTIAL,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions,
)
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery import (
    RouteStopServiceTimeRequest,
    parse_update_route_stop_service_time_request,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_stop_event
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import (
    emit_route_solution_stop_updated,
    notify_route_solution_stops_batch_updated,
)

from ..clone import clone_route_solution
from .update_route_stop_position import (
    _dedupe_and_sort_stops,
    _is_route_solution_end_date_valid,
    _mark_suffix_as_stale,
    _orders_by_id_for_route_solution,
    _validate_route_solution_orders_have_coordinates,
)


def update_route_stop_service_time(
    ctx: ServiceContext,
    route_stop_id: int,
    request: RouteStopServiceTimeRequest | dict[str, Any],
):
    parsed = (
        request
        if isinstance(request, RouteStopServiceTimeRequest)
        else parse_update_route_stop_service_time_request(request)
    )

    route_stop: RouteSolutionStop = get_instance(
        ctx=ctx,
        model=RouteSolutionStop,
        value=route_stop_id,
    )
    if not route_stop.route_solution_id:
        raise ValidationFailed("Route stop is missing route_solution_id.")

    route_solution: RouteSolution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=route_stop.route_solution_id,
    )

    _is_route_solution_end_date_valid(route_solution)
    _validate_route_solution_orders_have_coordinates(route_solution)

    original_route_solution = None
    if route_solution.is_optimized == IS_OPTIMIZED_OPTIMIZE:
        route_solution, stop_map, original_route_solution = clone_route_solution(
            route_solution
        )
        route_stop = stop_map.get(route_stop.id)
        if not route_stop:
            raise ValidationFailed("Route stop not found in cloned route solution.")

    if route_stop.service_time == parsed.service_time:
        return {
            "route_solution": serialize_route_solutions([route_solution], ctx),
            "route_solution_stops": [],
        }

    route_stop.service_time = parsed.service_time
    touched_stops: list[RouteSolutionStop] = [route_stop]

    if route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
        route_solution.is_optimized = IS_OPTIMIZED_PARTIAL

    refreshed_stops: list[RouteSolutionStop] = []
    recompute_from_position = max(1, int(route_stop.stop_order or 1))
    try:
        refreshed_stops = refresh_route_solution_incremental(
            route_solution=route_solution,
            time_zone=ctx.time_zone,
            orders_by_id=_orders_by_id_for_route_solution(route_solution),
            recompute_from_position=recompute_from_position,
        )
    except ValidationFailed:
        raise
    except Exception as exc:
        _mark_suffix_as_stale(route_solution, recompute_from_position)
        ctx.set_warning(
            f"Route timings could not be refreshed after service-time update: {exc}"
        )

    changed_stops = _dedupe_and_sort_stops(touched_stops + refreshed_stops)
    db.session.add(route_solution)
    if original_route_solution is not None:
        db.session.add(original_route_solution)
    if changed_stops:
        db.session.add_all(changed_stops)
    db.session.commit()

    # Emit real-time socket events for all affected stops (per-stop for precise UI updates).
    # Notifications are suppressed here (notify=False) and batched into one below.
    team_id = route_solution.team_id
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
    for stop in changed_stops:
        create_route_solution_stop_event(
            ctx=ctx,
            team_id=team_id,
            route_solution_stop_id=stop.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
            payload={
                "service_time": stop.service_time,
                "expected_arrival_time": stop.expected_arrival_time.isoformat() if stop.expected_arrival_time else None,
                "expected_departure_time": stop.expected_departure_time.isoformat() if stop.expected_departure_time else None,
            },
        )
        emit_route_solution_stop_updated(stop, notify=False, actor=actor)

    notify_route_solution_stops_batch_updated(
        route_solution=route_solution,
        affected_stop_count=len(changed_stops),
        change_hint="service_time_updated",
        actor=actor,
    )

    return {
        "route_solution": serialize_route_solutions([route_solution], ctx),
        "route_solution_stops": serialize_route_solution_stops(changed_stops, ctx),
    }
