from typing import Any, List
from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed, NotFound
from Delivery_app_BK.models import RouteSolution, RouteSolutionStop,RoutePlan, db
from Delivery_app_BK.directions import refresh_route_solution_incremental
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_OPTIMIZE,
    IS_OPTIMIZED_PARTIAL,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import clear_expected_stop_schedule
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_stop_event
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import emit_route_solution_stop_updated
from ..clone import clone_route_solution
from ..serializers import (
    serialize_stop_short,
)


def _ensure_utc(value: datetime | None) -> datetime | None:
    if not value:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _normalize_legacy_single_day_end_date(
    route_plan: RoutePlan,
    end_date: datetime | None,
) -> datetime | None:
    if not end_date:
        return end_date

    if getattr(route_plan, "date_strategy", None) != "single":
        return end_date

    start_date = _ensure_utc(getattr(route_plan, "start_date", None))
    if not start_date:
        return end_date

    # Legacy broken writes stored single-day plans at 00:00:00 instead of end-of-day.
    if (
        end_date.date() == start_date.date()
        and end_date.hour == 0
        and end_date.minute == 0
        and end_date.second == 0
        and end_date.microsecond == 0
    ):
        return end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    return end_date


def update_route_stop_position(
    ctx: ServiceContext,
    route_stop_id: int,
    position: int,
):

    if position < 1:
        raise ValidationFailed("position must be a positive integer.")

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
            raise ValidationFailed("Route stop not found on route solution.")

    stops: List[RouteSolutionStop] = list(route_solution.stops or [])

    if not stops:
        raise ValidationFailed("Route solution has no stops to reorder.")

    if route_stop.stop_order is None:
        raise ValidationFailed("Route stop has no stop_order to update.")

    max_position = max(stop.stop_order or 0 for stop in stops)


    if position > max_position:
        raise ValidationFailed("position exceeds the current stop range.")

    current_position = route_stop.stop_order
    if position == current_position:

        return {
            "route_solution": serialize_route_solutions([route_solution], ctx),
            "route_solution_stops": [],
        }


    touched_stops: list[RouteSolutionStop] = [route_stop]

    if position < current_position:
        for stop in stops:
            if stop.order_id == route_stop.order_id:
                continue
            if position <= (stop.stop_order or 0) < current_position:
                stop.stop_order = (stop.stop_order or 0) + 1
                stop.eta_status = "estimated"
                touched_stops.append(stop)
    else:
        for stop in stops:

            if stop.order_id == route_stop.order_id:

                continue
            if current_position < (stop.stop_order or 0) <= position:
                stop.stop_order = (stop.stop_order or 0) - 1
                stop.eta_status = "estimated"
                touched_stops.append(stop)


    route_stop.stop_order = position
    route_stop.eta_status = "estimated"
    affected_start_position = min(current_position, position)


    if route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
        route_solution.is_optimized = IS_OPTIMIZED_PARTIAL
    
    effective_time_zone = ctx.time_zone
    orders_by_id = _orders_by_id_for_route_solution(route_solution)
    try:
        refreshed_stops = refresh_route_solution_incremental(
            route_solution=route_solution,
            time_zone=effective_time_zone,
            orders_by_id=orders_by_id,
            recompute_from_position=affected_start_position,
        )
    except ValidationFailed:
        raise
    except Exception as exc:
        _mark_suffix_as_stale(route_solution, affected_start_position)
        refreshed_stops = []
        ctx.set_warning(
            f"Route timings could not be refreshed after stop reorder: {exc}"
        )

   
  
    db.session.add(route_solution)
    
    # Store final positions before updating to temporary values
    # This avoids unique constraint violations when multiple stops change positions
    # Use object identity here because cloned optimized-route stops may not have
    # stable DB ids until after the intermediate flush.
    final_positions = {id(stop): stop.stop_order for stop in touched_stops}
    
    # Phase 1: Assign temporary negative positions to clear constraint violations
    for idx, stop in enumerate(touched_stops):
        stop.stop_order = -(idx + 1)
    
    db.session.add_all(_dedupe_and_sort_stops(touched_stops + refreshed_stops))
    if original_route_solution is not None:
        db.session.add(original_route_solution)
    db.session.flush()
    
    # Phase 2: Assign final positions now that temporary positions are in place
    for stop in touched_stops:
        stop.stop_order = final_positions[id(stop)]
    
    db.session.add_all(_dedupe_and_sort_stops(touched_stops))
    db.session.commit()

    # Emit real-time events for all affected stops
    team_id = route_solution.team_id
    all_affected_stops = _dedupe_and_sort_stops(touched_stops + refreshed_stops)
    for stop in all_affected_stops:
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
        "route_solution": serialize_route_solutions([route_solution], ctx),
        "route_solution_stops": serialize_route_solution_stops(
            all_affected_stops,
            ctx,
        ),
    }



def _is_route_solution_end_date_valid (route_solution:RouteSolution):
    try:
        route_plan:RoutePlan = route_solution.route_group.route_plan
        if route_plan:
            now = datetime.now(timezone.utc)
            start_date = _ensure_utc(route_plan.start_date) or now
            end_date = _ensure_utc(route_plan.end_date) or start_date
            end_date = _normalize_legacy_single_day_end_date(route_plan, end_date)
            
    except Exception:
        raise NotFound('route solution has no route group or route plan linked.')
    
    if end_date < now:
        raise ValidationFailed('This route has already finished and its stop order cannot be changed. Update the delivery plan end date to a future time to modify the stop order.')


def _orders_by_id_for_route_solution(route_solution: RouteSolution) -> dict[int, object]:
    route_plan = None
    if route_solution.route_group:
        route_plan = route_solution.route_group.route_plan
    if not route_plan:
        return {}

    return {
        order.id: order
        for order in (route_plan.orders or [])
        if getattr(order, "id", None) is not None
    }


def _validate_route_solution_orders_have_coordinates(route_solution: RouteSolution) -> None:
    orders_by_id = _orders_by_id_for_route_solution(route_solution)
    invalid_order_ids: list[int] = []
    invalid_order_client_ids: list[str] = []

    seen_order_ids: set[int] = set()
    for stop in (route_solution.stops or []):
        order_id = getattr(stop, "order_id", None)
        if order_id is None or order_id in seen_order_ids:
            continue
        seen_order_ids.add(order_id)

        order = orders_by_id.get(order_id)
        order_client_id = getattr(order, "client_id", None) if order else None
        location = getattr(order, "client_address", None) if order else None
        if _coordinates_from_location(location) is None:
            invalid_order_ids.append(order_id)
            if order_client_id:
                invalid_order_client_ids.append(str(order_client_id))

    if invalid_order_ids:
        client_ids_suffix = (
            f" client_ids={sorted(set(invalid_order_client_ids))}"
            if invalid_order_client_ids
            else ""
        )
        raise ValidationFailed(
            "Cannot reorder route stop: missing valid coordinates for orders "
            f"{sorted(invalid_order_ids)}.{client_ids_suffix}"
        )


def _coordinates_from_location(location: dict[str, Any] | None) -> tuple[float, float] | None:
    if not location:
        return None
    candidate = location.get("coordinates", location)
    if not isinstance(candidate, dict):
        return None

    lat = candidate.get("lat") or candidate.get("latitude")
    lng = candidate.get("lng") or candidate.get("longitude")
    if lat is None or lng is None:
        return None

    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _dedupe_and_sort_stops(stops: list[RouteSolutionStop]) -> list[RouteSolutionStop]:
    deduped: list[RouteSolutionStop] = []
    seen: set[int] = set()
    for stop in stops:
        stop_id = getattr(stop, "id", None)
        if stop_id in seen:
            continue
        if stop_id is not None:
            seen.add(stop_id)
        deduped.append(stop)
    return sorted(
        deduped,
        key=lambda stop: stop.stop_order if stop.stop_order is not None else 0,
    )


def _mark_suffix_as_stale(route_solution: RouteSolution, start_position: int) -> None:
    start_position = max(1, int(start_position or 1))
    route_solution.end_leg_polyline = None
    if start_position <= 1:
        route_solution.start_leg_polyline = None

    anchor_position = start_position - 1
    for stop in route_solution.stops or []:
        stop_order = stop.stop_order or 0
        if stop_order >= start_position:
            clear_expected_stop_schedule(stop)
            stop.eta_status = "stale"
            stop.in_range = False
            stop.reason_was_skipped = "Route timing unavailable"
            stop.has_constraint_violation = False
            stop.constraint_warnings = None
            stop.to_next_polyline = None
        elif anchor_position >= 1 and stop_order == anchor_position:
            stop.to_next_polyline = None
