from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, db
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_OPTIMIZE,
    IS_OPTIMIZED_PARTIAL,
)
from Delivery_app_BK.directions import refresh_route_solution_incremental
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions,
)
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery import (
    RouteStopGroupPositionRequest,
    parse_update_route_stop_group_position_request,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_stop_event
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import emit_route_solution_stop_updated

from ..clone import clone_route_solution
from .update_route_stop_position import (
    _dedupe_and_sort_stops,
    _is_route_solution_end_date_valid,
    _mark_suffix_as_stale,
    _orders_by_id_for_route_solution,
    _validate_route_solution_orders_have_coordinates,
)


def update_route_stop_group_position(
    ctx: ServiceContext,
    request: RouteStopGroupPositionRequest | dict[str, Any],
):
    parsed = (
        request
        if isinstance(request, RouteStopGroupPositionRequest)
        else parse_update_route_stop_group_position_request(request)
    )

    route_solution: RouteSolution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=parsed.route_solution_id,
    )

    _is_route_solution_end_date_valid(route_solution)
    _validate_route_solution_orders_have_coordinates(route_solution)

    original_route_solution = None
    route_stop_ids = parsed.route_stop_ids
    anchor_stop_id = parsed.anchor_stop_id

    if route_solution.is_optimized == IS_OPTIMIZED_OPTIMIZE:
        route_solution, stop_map, original_route_solution = clone_route_solution(route_solution)

        mapped_route_stop_ids: list[int] = []
        for stop_id in route_stop_ids:
            mapped = stop_map.get(stop_id)
            if not mapped or mapped.id is None:
                raise ValidationFailed(f'Route stop {stop_id} is not available in cloned route solution.')
            mapped_route_stop_ids.append(mapped.id)

        mapped_anchor_stop = stop_map.get(anchor_stop_id)
        if not mapped_anchor_stop or mapped_anchor_stop.id is None:
            raise ValidationFailed('anchor_stop_id is not available in cloned route solution.')

        route_stop_ids = mapped_route_stop_ids
        anchor_stop_id = mapped_anchor_stop.id

    stops = (
        db.session.query(RouteSolutionStop)
        .filter(RouteSolutionStop.route_solution_id == route_solution.id)
        .order_by(RouteSolutionStop.stop_order.asc(), RouteSolutionStop.id.asc())
        .with_for_update()
        .all()
    )

    if not stops:
        raise ValidationFailed('Route solution has no stops to reorder.')

    stop_by_id = {
        stop.id: stop
        for stop in stops
        if stop.id is not None
    }

    if anchor_stop_id not in stop_by_id:
        raise ValidationFailed('anchor_stop_id does not belong to route solution.')

    moving_ids_set = set(route_stop_ids)
    if anchor_stop_id in moving_ids_set:
        raise ValidationFailed('anchor_stop_id cannot be inside moving block.')

    missing_route_stop_ids = [stop_id for stop_id in route_stop_ids if stop_id not in stop_by_id]
    if missing_route_stop_ids:
        raise ValidationFailed(
            f'route_stop_ids contains stops that do not belong to route solution: {missing_route_stop_ids}'
        )

    current_ordered_ids = [stop.id for stop in stops if stop.id is not None]
    remaining_ids = [stop_id for stop_id in current_ordered_ids if stop_id not in moving_ids_set]

    max_position = len(remaining_ids) + 1
    if parsed.position < 1 or parsed.position > max_position:
        raise ValidationFailed(
            f'position must be within 1..{max_position} after removing the moving block.'
        )

    insert_index = parsed.position - 1
    next_ordered_ids = [
        *remaining_ids[:insert_index],
        *route_stop_ids,
        *remaining_ids[insert_index:],
    ]

    if next_ordered_ids == current_ordered_ids:
        return {
            'route_solution': serialize_route_solutions([route_solution], ctx),
            'route_solution_stops': serialize_route_solution_stops(stops, ctx),
        }

    first_changed_index = 0
    while (
        first_changed_index < len(current_ordered_ids)
        and current_ordered_ids[first_changed_index] == next_ordered_ids[first_changed_index]
    ):
        first_changed_index += 1

    ordered_stops = [stop_by_id[stop_id] for stop_id in next_ordered_ids]
    touched_stops: list[RouteSolutionStop] = []
    next_positions: dict[int, int] = {}  # Store final positions without updating yet
    for index, stop in enumerate(ordered_stops):
        next_stop_order = index + 1
        previous_stop_order = stop.stop_order
        if previous_stop_order != next_stop_order:
            next_positions[stop.id] = next_stop_order
            stop.eta_status = 'estimated'
            touched_stops.append(stop)
            continue

        if index >= first_changed_index:
            stop.eta_status = 'estimated'
            touched_stops.append(stop)

    if route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
        route_solution.is_optimized = IS_OPTIMIZED_PARTIAL

    recompute_from_position = first_changed_index + 1
    refreshed_stops: list[RouteSolutionStop] = []
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
            f'Route timings could not be refreshed after grouped stop reorder: {exc}'
        )

    changed_stops = _dedupe_and_sort_stops(touched_stops + refreshed_stops)

    db.session.add(route_solution)
    if original_route_solution is not None:
        db.session.add(original_route_solution)
    
    # Phase 1: Assign temporary negative positions to clear constraint violations
    # Only need to do this if we have position changes
    if next_positions:
        for idx, stop in enumerate(touched_stops):
            if stop.id in next_positions:
                stop.stop_order = -(idx + 1)
        
        if changed_stops:
            db.session.add_all(changed_stops)
        db.session.flush()
        
        # Phase 2: Assign final positions now that temporary positions are in place
        for stop in touched_stops:
            if stop.id in next_positions:
                stop.stop_order = next_positions[stop.id]
    
    if changed_stops:
        db.session.add_all(changed_stops)
    db.session.commit()

    # Emit real-time events for all affected stops
    team_id = route_solution.team_id
    for stop in changed_stops:
        create_route_solution_stop_event(
            ctx=ctx,
            team_id=team_id,
            route_solution_stop_id=stop.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
            payload={
                "stop_order": stop.stop_order,
                "expected_arrival_time": stop.expected_arrival_time.isoformat() if stop.expected_arrival_time else None,
                "expected_departure_time": stop.expected_departure_time.isoformat() if stop.expected_departure_time else None,
            },
        )
        emit_route_solution_stop_updated(stop)

    return {
        'route_solution': serialize_route_solutions([route_solution], ctx),
        'route_solution_stops': serialize_route_solution_stops(changed_stops, ctx),
    }
