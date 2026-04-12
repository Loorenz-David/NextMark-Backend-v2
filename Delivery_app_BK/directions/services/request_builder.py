from __future__ import annotations

from datetime import datetime, time as time_cls, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Order, RouteSolution, RouteSolutionStop
from Delivery_app_BK.services.domain.delivery_plan.local_delivery import (
    calculate_service_time_seconds,
    combine_plan_date_and_local_hhmm_to_utc,
    ensure_utc_datetime,
    normalize_service_time_payload,
    parse_duration_seconds,
    parse_hhmm,
    resolve_effective_service_time_payload,
    resolve_request_timezone,
    resolve_order_item_quantity,
)

from Delivery_app_BK.directions.domain.models import (
    DirectionsRequest,
    DirectionsRequestBuildResult,
    DirectionsStopInput,
    DirectionsVisitGroup,
    DirectionsVisitStopMember,
)
from Delivery_app_BK.route_optimization.constants.route_end_strategy import (
    ROUND_TRIP,
    CUSTOM_END_ADDRESS,
    LAST_STOP,
)

DEFAULT_TRAVEL_MODE = "DRIVING"
DEFAULT_ROUTE_MODIFIERS = {
    "avoid_tolls": False,
    "avoid_highways": False,
    "avoid_ferries": False,
}

logger = logging.getLogger(__name__)


def build_directions_request(
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order],
    consider_traffic: bool = True,
    time_zone: str = None,
    recompute_from_position: int = 1,
) -> DirectionsRequest:
    build_result = build_directions_request_bundle(
        route_solution=route_solution,
        orders_by_id=orders_by_id,
        consider_traffic=consider_traffic,
        time_zone=time_zone,
        recompute_from_position=recompute_from_position,
    )
    return build_result.request


def build_directions_request_bundle(
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order],
    consider_traffic: bool = True,
    time_zone: str | None = None,
    recompute_from_position: int = 1,
) -> DirectionsRequestBuildResult:
    stops: List[RouteSolutionStop] = [stop for stop in (route_solution.stops or []) if stop.order_id]
    stops.sort(key=lambda stop: stop.stop_order or 0)
    if not stops:
        raise ValidationFailed("Route solution has no stops with orders.")

    requested_start_position = max(1, int(recompute_from_position or 1))
    full_recompute = requested_start_position <= 1
    effective_start_position = 1
    anchor_stop: RouteSolutionStop | None = None
    recalculated_stops = stops

    if not full_recompute:
        anchor_stop = _find_stop_by_position(stops, requested_start_position - 1)
        recalculated_stops = [
            stop
            for stop in stops
            if (stop.stop_order or 0) >= requested_start_position
        ]
        if not _can_use_anchor(anchor_stop, orders_by_id):
            full_recompute = True
            anchor_stop = None
            recalculated_stops = stops
            effective_start_position = 1
        else:
            effective_start_position = requested_start_position

    origin_location = _resolve_origin_location(
        route_solution=route_solution,
        stops=stops,
        orders_by_id=orders_by_id,
        anchor_stop=anchor_stop,
    )
    destination_location = _resolve_destination_location(
        route_solution=route_solution,
        stops=stops,
        orders_by_id=orders_by_id,
        origin_location=origin_location,
    )

    origin_coordinates = _coordinates_from_location(origin_location)
    destination_coordinates = _coordinates_from_location(destination_location)
    if not origin_coordinates or not destination_coordinates:
        raise ValidationFailed("Origin or destination is missing coordinates.")

    default_service_time = normalize_service_time_payload(
        route_solution.stops_service_time
    )
    intermediates, visit_groups = _build_intermediates(
        recalculated_stops,
        orders_by_id,
        default_service_time=default_service_time,
    )
    if full_recompute and not intermediates:
        raise ValidationFailed("Route solution has no stops with valid coordinates.")

    departure_time = _resolve_recompute_departure_time(
        route_solution=route_solution,
        orders_by_id=orders_by_id,
        time_zone=time_zone,
        anchor_stop=anchor_stop,
        default_service_time=default_service_time,
    )

    request = DirectionsRequest(
        origin=origin_coordinates,
        destination=destination_coordinates,
        intermediates=intermediates,
        travel_mode=DEFAULT_TRAVEL_MODE,
        consider_traffic=consider_traffic,
        route_modifiers=dict(DEFAULT_ROUTE_MODIFIERS),
        departure_time=departure_time,
    )

    return DirectionsRequestBuildResult(
        request=request,
        full_recompute=full_recompute,
        effective_start_position=effective_start_position,
        anchor_order_id=anchor_stop.order_id if anchor_stop else None,
        affected_order_ids=[stop.order_id for stop in recalculated_stops if stop.order_id],
        visit_groups=visit_groups,
    )


def _find_stop_by_position(
    stops: list[RouteSolutionStop],
    position: int,
) -> RouteSolutionStop | None:
    for stop in stops:
        if (stop.stop_order or 0) == position:
            return stop
    return None


def _can_use_anchor(
    anchor_stop: RouteSolutionStop | None,
    orders_by_id: Dict[int, Order],
) -> bool:
    if not anchor_stop or not anchor_stop.order_id:
        return False
    if anchor_stop.expected_arrival_time is None:
        return False
    anchor_order = orders_by_id.get(anchor_stop.order_id)
    if not anchor_order:
        return False
    return _coordinates_from_location(anchor_order.client_address) is not None


def _resolve_origin_location(
    route_solution: RouteSolution,
    stops: list[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
    anchor_stop: RouteSolutionStop | None,
) -> Dict[str, Any] | None:
    if anchor_stop and anchor_stop.order_id:
        anchor_order = orders_by_id.get(anchor_stop.order_id)
        if anchor_order and anchor_order.client_address:
            return anchor_order.client_address

    origin_location = route_solution.start_location
    first_order = orders_by_id.get(stops[0].order_id) if stops else None
    return origin_location or (first_order.client_address if first_order else None)


def _resolve_destination_location(
    route_solution: RouteSolution,
    stops: list[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
    origin_location: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    route_end_strategy = route_solution.route_end_strategy
    if route_end_strategy == ROUND_TRIP:
        destination_location = route_solution.start_location or origin_location
    elif route_end_strategy == LAST_STOP:
        destination_location = _infer_location_from_stops(stops, orders_by_id)
    else:
        destination_location = route_solution.end_location

    last_order = orders_by_id.get(stops[-1].order_id) if stops else None
    return destination_location or (
        last_order.client_address if last_order else origin_location
    )


def _build_intermediates(
    stops: list[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
    *,
    default_service_time: dict | None,
) -> tuple[list[DirectionsStopInput], list[DirectionsVisitGroup]]:
    intermediates: list[DirectionsStopInput] = []
    visit_groups: list[DirectionsVisitGroup] = []

    for stop in stops:
        if not stop.order_id:
            continue
        order = orders_by_id.get(stop.order_id)
        if not order:
            continue
        coords = _coordinates_from_location(order.client_address)
        if not coords:
            raise ValidationFailed(f"Order {order.id} is missing coordinates.")
        service_duration_seconds = _resolve_stop_service_duration_seconds(
            stop=stop,
            order=order,
            default_service_time=default_service_time,
        )
        normalized_service_seconds = int(service_duration_seconds or 0)
        member = DirectionsVisitStopMember(
            stop_id=getattr(stop, "id", None),
            order_id=order.id,
            service_duration_seconds=normalized_service_seconds,
        )
        location_key = _location_group_key(coords)

        if (
            visit_groups
            and visit_groups[-1].location_key == location_key
        ):
            previous_group = visit_groups[-1]
            visit_groups[-1] = DirectionsVisitGroup(
                location=previous_group.location,
                location_key=previous_group.location_key,
                members=[*previous_group.members, member],
            )
            previous_input = intermediates[-1]
            intermediates[-1] = DirectionsStopInput(
                order_id=previous_input.order_id,
                location=previous_input.location,
                service_duration_seconds=(
                    int(previous_input.service_duration_seconds or 0)
                    + normalized_service_seconds
                ),
            )
            continue

        visit_groups.append(
            DirectionsVisitGroup(
                location=coords,
                location_key=location_key,
                members=[member],
            )
        )
        intermediates.append(
            DirectionsStopInput(
                order_id=order.id,
                location=coords,
                service_duration_seconds=normalized_service_seconds,
            )
        )
    return intermediates, visit_groups


def _resolve_recompute_departure_time(
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order],
    time_zone: str | None,
    anchor_stop: RouteSolutionStop | None,
    default_service_time: dict | None,
) -> Optional[datetime]:
    if anchor_stop and anchor_stop.expected_arrival_time:
        departure_time = _coerce_datetime(anchor_stop.expected_arrival_time)
        if departure_time is not None:
            anchor_order = (
                orders_by_id.get(anchor_stop.order_id)
                if anchor_stop.order_id is not None
                else None
            )
            service_seconds = _resolve_stop_service_duration_seconds(
                stop=anchor_stop,
                order=anchor_order,
                default_service_time=default_service_time,
            ) or 0
            return departure_time + timedelta(seconds=service_seconds)
    return _resolve_departure_time(route_solution, orders_by_id, time_zone=time_zone)


def build_time_windows(
    order: Order,
    base_date: Optional[datetime],
    base_end_date: Optional[datetime] = None,
) -> List[Tuple[datetime, datetime]]:
    return []


def _coordinates_from_location(location: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
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
        return {"latitude": float(lat), "longitude": float(lng)}
    except (TypeError, ValueError):
        return None


def _infer_location_from_stops(
    stops: List[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
) -> Optional[Dict[str, Any]]:
    last_stop = _select_last_stop(stops)
    if not last_stop:
        return None
    order = getattr(last_stop, "order", None)
    if not order and last_stop.order_id is not None:
        order = orders_by_id.get(last_stop.order_id)
    if order and order.client_address:
        return order.client_address
    return None


def _select_last_stop(stops: List[RouteSolutionStop]) -> Optional[RouteSolutionStop]:
    eligible = [stop for stop in stops if stop.stop_order is not None]
    if not eligible:
        return None
    return max(eligible, key=lambda stop: stop.stop_order)


def _resolve_departure_time(
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order],
    time_zone: str = None
) -> Optional[datetime]:
    now = datetime.now(timezone.utc)

    plan_start = None
    timezone_plan = None
    route_group = getattr(route_solution, "route_group", None)
    if route_group is not None:
        plan = getattr(route_group, "route_plan", None)
        timezone_plan = route_group
        if plan is not None and getattr(plan, "start_date", None):
            plan_start = _coerce_datetime(plan.start_date)

    request_timezone = resolve_request_timezone(
        plan_instance=timezone_plan,
        identity={"time_zone": time_zone} if time_zone else None,
    )

    if route_solution.set_start_time:
        parsed = _coerce_datetime(route_solution.set_start_time)
        if parsed:
            return parsed
        time_only = parse_hhmm(route_solution.set_start_time)
        if time_only:
            resolved_departure = combine_plan_date_and_local_hhmm_to_utc(
                plan_date=plan_start or now,
                hhmm=route_solution.set_start_time,
                tz=request_timezone,
            )
            return resolved_departure

    if plan_start:
        plan_start = ensure_utc_datetime(plan_start)
        return plan_start

    return now + timedelta(minutes=5)


def _parse_time_string(value: Optional[str]) -> Optional[time_cls]:
    if not value:
        return None
    parsed = str(value).strip()
    if not parsed:
        return None
    parts = parsed.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return time_cls(hour=hour, minute=minute, second=second)
    except ValueError:
        return None


def _resolve_stop_service_duration_seconds(
    stop: RouteSolutionStop,
    order: Order | None,
    *,
    default_service_time: dict | None,
) -> int | None:
    item_quantity = resolve_order_item_quantity(order) if order is not None else 0
    effective_service_time = resolve_effective_service_time_payload(
        getattr(stop, "service_time", None),
        default_service_time,
    )
    if effective_service_time is not None:
        service_minutes = calculate_service_time_seconds(
            effective_service_time,
            item_quantity,
        )
        if service_minutes is not None:
            return int(service_minutes) * 60
    return parse_duration_seconds(getattr(stop, "service_duration", None))


def _location_group_key(location: Dict[str, float]) -> str:
    return (
        f"{float(location['latitude']):.6f},"
        f"{float(location['longitude']):.6f}"
    )


def _coerce_datetime(value: Any, tz = timezone.utc) -> Optional[datetime]:
    if not value:
        return None
   
    if isinstance(value, datetime):
        return value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)

    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)   

    return parsed
