from __future__ import annotations

from datetime import datetime, time as time_cls, timezone, timedelta
from typing import Any, Dict, List, Optional

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.domain.models import (
    OptimizationContext,
    OptimizationRequest,
    SkippedShipment,
    Shipment,
    ShipmentMember,
    TimeWindow,
)
from Delivery_app_BK.services.domain.delivery_plan.local_delivery import (
    calculate_service_time_seconds,
    combine_plan_date_and_local_hhmm_to_utc,
    normalize_service_time_payload,
    parse_duration_seconds,
    resolve_effective_service_time_payload,
    resolve_request_timezone,
    resolve_order_item_quantity,
)
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP,  LAST_STOP
from Delivery_app_BK.route_optimization.constants.skip_reasons import (
    OUTSIDE_OPTIMIZATION_WINDOW,
)
from Delivery_app_BK.domain.vehicle.travel_mode import map_to_google_travel_mode

DEFAULT_ROUTE_MODIFIERS = {
    "avoid_tolls": False,
    "avoid_highways": False,
    "avoid_ferries": False,
    "avoid_indoor": False,
}

DEFAULT_OBJECTIVES: List[Dict[str, Any]] = []

DEFAULT_VEHICLE_VALUES = {
    "cost_per_kilometer": 1.0,
    "travel_mode": "DRIVING",
}


def build_request(context: OptimizationContext) -> OptimizationRequest:
    incoming_data = context.incoming_data
    route_group = getattr(context, "route_group", None)
    if route_group is None:
        route_group = context.local_delivery_plan
    route_plan = getattr(context, "route_plan", None)
    if route_plan is None:
        route_plan = context.delivery_plan

    start_location = (
        incoming_data.get("start_location")
        or context.route_solution.start_location
        or _infer_location_from_orders(
            context.orders,
            context.route_solution.stops,
            prefer="lowest",
        )
    )

    if context.route_end_strategy == ROUND_TRIP:
        end_location = start_location
    elif context.route_end_strategy == LAST_STOP:
        end_location = _infer_location_from_orders(
            context.orders,
            context.route_solution.stops,
            prefer="highest",
        )
    else:
        end_location = (
            incoming_data.get("end_location")
            or context.route_solution.end_location
            or start_location
        )

    

    _ensure_address_format(start_location, "start_location")
    _ensure_address_format(end_location, "end_location")

    start_coordinates = _coordinates_from_location(start_location)
    end_coordinates = _coordinates_from_location(end_location)
    if not start_coordinates or not end_coordinates:
        raise ValidationFailed("Start or end location is missing coordinates.")

    global_start_time, global_end_time = _resolve_global_time_bounds(
        context,
        incoming_data,
    )

    shipments, pre_skipped_shipments, excluded_shipments = _build_shipments(
        context,
        global_start_time=global_start_time,
        global_end_time=global_end_time,
    )

    route_modifiers = dict(DEFAULT_ROUTE_MODIFIERS)
    if isinstance(incoming_data.get("route_modifiers"), dict):
        for key, value in incoming_data["route_modifiers"].items():
            if key in route_modifiers:
                route_modifiers[key] = bool(value)

    objectives = _coerce_objectives(incoming_data.get("objectives"))

    vehicle_config = incoming_data.get("vehicle", {})
    travel_mode = vehicle_config.get("travel_mode", DEFAULT_VEHICLE_VALUES["travel_mode"])
    cost_per_kilometer = vehicle_config.get(
        "cost_per_kilometer", DEFAULT_VEHICLE_VALUES["cost_per_kilometer"]
    )

    # Override with canonical vehicle data when the route solution has an assigned vehicle
    if context.vehicle is not None:
        vehicle = context.vehicle
        if getattr(vehicle, "travel_mode", None):
            travel_mode = map_to_google_travel_mode(vehicle.travel_mode)
        if getattr(vehicle, "cost_per_km", None) is not None:
            cost_per_kilometer = float(vehicle.cost_per_km)

    return OptimizationRequest(
        route_plan_id=route_plan.id,
        route_group_id=route_group.id,
        delivery_plan_id=route_plan.id,
        local_delivery_plan_id=route_group.id,
        route_solution_id=context.route_solution.id,
        shipments=shipments,
        start_location=start_location,
        end_location=end_location,
        start_coordinates=start_coordinates,
        end_coordinates=end_coordinates,
        global_start_time=global_start_time,
        global_end_time=global_end_time,
        consider_traffic=bool(incoming_data.get("consider_traffic")),
        route_modifiers=route_modifiers,
        objectives=objectives,
        travel_mode=travel_mode,
        cost_per_kilometer=float(cost_per_kilometer),
        pre_skipped_shipments=pre_skipped_shipments,
        excluded_shipments=excluded_shipments,
        populate_transition_polylines=bool(
            incoming_data.get("populate_transition_polylines", True)
        ),
        injected_routes=_build_injected_routes(context, incoming_data),
        interpret_injected_solutions_using_labels=context.interpret_injected_solutions_using_labels,
    )


def _build_shipments(
    context: OptimizationContext,
    *,
    global_start_time: Optional[datetime],
    global_end_time: Optional[datetime],
) -> tuple[List[Shipment], List[SkippedShipment], List[Shipment]]:
    service_durations = _parse_service_durations(context.incoming_data)
    stop_by_order_id = {
        stop.order_id: stop
        for stop in (context.route_solution.stops or [])
        if getattr(stop, "order_id", None) is not None
    }
    default_service_time = normalize_service_time_payload(
        context.route_solution.stops_service_time
    )
    shipments: List[Shipment] = []
    pre_skipped_shipments: List[SkippedShipment] = []
    excluded_shipments: List[Shipment] = []
    grouped_shipments: dict[str, dict[str, Any]] = {}

    for order in _ordered_orders_for_shipments(context):
        coords = _coordinates_from_location(order.client_address)
        if not coords:
            raise ValidationFailed(f"Order {order.id} is missing coordinates.")

        stop = stop_by_order_id.get(order.id)
        service_duration_seconds = _resolve_order_service_duration_seconds(
            order=order,
            stop=stop,
            service_durations=service_durations,
            default_service_time=default_service_time,
        )
        location_key = _location_group_key(coords)
        shipment = grouped_shipments.get(location_key)
        if shipment is None:
            shipment = {
                "label": _shipment_group_label(context.route_solution.id, location_key),
                "location": coords,
                "members": [],
                "time_windows": _build_time_windows(order, context),
                "service_duration_seconds": 0,
            }
            grouped_shipments[location_key] = shipment

        shipment["members"].append(
            ShipmentMember(
                order_id=order.id,
                service_duration_seconds=int(service_duration_seconds or 0),
            )
        )
        shipment["service_duration_seconds"] += int(service_duration_seconds or 0)

    for shipment in grouped_shipments.values():
        members = list(shipment["members"])
        shipment_time_windows = list(shipment["time_windows"] or [])
        if len(members) == 1:
            effective_windows = _intersect_windows_with_global_bounds(
                shipment_time_windows,
                global_start_time=global_start_time,
                global_end_time=global_end_time,
            )
            if shipment_time_windows and not effective_windows:
                excluded_shipments.append(
                    Shipment(
                        label=shipment["label"],
                        location=shipment["location"],
                        members=members,
                        time_windows=shipment_time_windows,
                        service_duration_seconds=int(shipment["service_duration_seconds"] or 0),
                    )
                )
                pre_skipped_shipments.append(
                    SkippedShipment(
                        shipment_label=shipment["label"],
                        reason=OUTSIDE_OPTIMIZATION_WINDOW,
                    )
                )
                continue
        else:
            effective_windows = []

        shipments.append(
            Shipment(
                label=shipment["label"],
                location=shipment["location"],
                members=members,
                time_windows=effective_windows,
                service_duration_seconds=int(shipment["service_duration_seconds"] or 0),
            )
        )

    return shipments, pre_skipped_shipments, excluded_shipments


def _build_time_windows(order, context: OptimizationContext) -> List[TimeWindow]:
    delivery_windows = _build_delivery_windows_from_order(order)
    if delivery_windows:
        return delivery_windows

    return []


def _build_delivery_windows_from_order(order) -> List[TimeWindow]:
    rows = list(getattr(order, "delivery_windows", None) or [])
    if not rows:
        return []

    if len(rows) > 14:
        raise ValidationFailed(f"Order {order.id} exceeds max delivery windows (14).")

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _coerce_datetime(getattr(row, "start_at", None)) or datetime.min.replace(tzinfo=timezone.utc),
            _coerce_datetime(getattr(row, "end_at", None)) or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )

    windows: List[TimeWindow] = []
    previous_end: Optional[datetime] = None
    for index, row in enumerate(sorted_rows):
        start = _coerce_datetime(getattr(row, "start_at", None))
        end = _coerce_datetime(getattr(row, "end_at", None))
        if not start or not end:
            raise ValidationFailed(
                f"Order {order.id} has invalid delivery window at index {index}.",
            )
        if end <= start:
            raise ValidationFailed(
                f"Order {order.id} has delivery window with end_at <= start_at at index {index}.",
            )
        if previous_end and start < previous_end:
            raise ValidationFailed(
                f"Order {order.id} has overlapping delivery windows.",
            )
        windows.append(TimeWindow(start_time=start, end_time=end))
        previous_end = end

    return windows


def _build_injected_routes(
    context: OptimizationContext,
    incoming_data: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    incoming_routes = incoming_data.get("injected_routes")
    if incoming_routes is not None:
        return incoming_routes

    if not context.interpret_injected_solutions_using_labels:
        return None

    route_solution = context.route_solution
    stops = list(route_solution.stops or [])
    if not stops:
        return None

    eligible_stops = [
        stop for stop in stops if stop.order_id and stop.eta_status != "stale"
    ]
    if not eligible_stops:
        return None

    eligible_stops.sort(key=lambda stop: stop.stop_order or 0)

    visited_group_labels: set[str] = set()
    visits: list[dict[str, str]] = []
    order_lookup = {
        order.id: order for order in context.orders if getattr(order, "id", None) is not None
    }
    for stop in eligible_stops:
        order = order_lookup.get(stop.order_id)
        if not order:
            continue
        coords = _coordinates_from_location(order.client_address)
        if not coords:
            continue
        group_label = _shipment_group_label(
            route_solution.id,
            _location_group_key(coords),
        )
        if group_label in visited_group_labels:
            continue
        visited_group_labels.add(group_label)
        visits.append({"shipment_label": group_label})

    return [
        {
            "vehicle_label": f"vehicle-{context.local_delivery_plan.id}",
            "visits": visits,
        }
    ]


def _build_date_range_windows(
    *,
    earliest: Optional[datetime],
    latest: Optional[datetime],
    preferred_start: Optional[time_cls],
    preferred_end: Optional[time_cls],
    context: OptimizationContext,
) -> List[TimeWindow]:
    max_windows = 14
    windows: List[TimeWindow] = []

    # ---- Resolve global bounds ----
    global_start, global_end = _resolve_global_time_bounds(
        context,
        context.incoming_data,
    )

    tz = _resolve_tz(global_start, global_end)

 
    # ---- Resolve date range ----
    range_start = earliest or _coerce_datetime(context.delivery_plan.start_date)
    range_end = latest or (range_start + timedelta(days=max_windows - 1))

    tz = range_start.tzinfo


    if global_start:
        global_start = global_start.astimezone(tz)
    if global_end:
        global_end = global_end.astimezone(tz)


    if range_start.tzinfo is None:
        range_start = range_start.replace(tzinfo=tz)
    else:
        range_start = range_start.astimezone(tz)

    if range_end.tzinfo is None:
        range_end = range_end.replace(tzinfo=tz)
    else:
        range_end = range_end.astimezone(tz)


    # Clamp date range to global bounds
    if global_start and (range_start < global_start or range_start > global_end):
        range_start = global_start
    if global_end and (range_end > global_end or range_end < global_start):
        range_end = global_end


   

    # ---- Iterate day by day ----
    current_day = range_start.date()
    last_day = range_end.date()

    while current_day <= last_day and len(windows) < max_windows:
        # default full-day
        day_start = time_cls(0, 0, 0)
        day_end   = time_cls(23, 59, 49)

        # first day → respect global_start
        if global_start and current_day == global_start.date():
            day_start = global_start.timetz().replace(tzinfo=None)

        # last day → respect global_end
        if global_end and current_day == global_end.date():
            day_end = global_end.timetz().replace(tzinfo=None)

        # preferred time overrides (if present)
        if preferred_start:
            day_start = max(day_start, preferred_start)
        if preferred_end:
            day_end = min(day_end, preferred_end)
       
        start_dt = datetime.combine(current_day, day_start, tzinfo=tz)
        end_dt   = datetime.combine(current_day, day_end,   tzinfo=tz)

        if end_dt >= start_dt:
            
            windows.append(TimeWindow(start_time=start_dt, end_time=end_dt))

        current_day += timedelta(days=1)

    return windows


def _intersect_windows_with_global_bounds(
    windows: List[TimeWindow],
    *,
    global_start_time: Optional[datetime],
    global_end_time: Optional[datetime],
) -> List[TimeWindow]:
    if not windows:
        return []
    if not global_start_time and not global_end_time:
        return list(windows)

    intersected: List[TimeWindow] = []
    for window in windows:
        start_time = window.start_time
        end_time = window.end_time
        if not start_time or not end_time:
            continue

        effective_start = max(start_time, global_start_time) if global_start_time else start_time
        effective_end = min(end_time, global_end_time) if global_end_time else end_time
        if effective_end <= effective_start:
            continue

        intersected.append(
            TimeWindow(
                start_time=effective_start,
                end_time=effective_end,
            )
        )
    return intersected



def _coerce_objectives(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list) and value:
        return value
    if isinstance(value, dict):
        return [value]
    return list(DEFAULT_OBJECTIVES)


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


def _ordered_orders_for_shipments(context: OptimizationContext) -> list[Any]:
    order_by_id = {
        order.id: order for order in context.orders if getattr(order, "id", None) is not None
    }
    ordered: list[Any] = []
    seen_order_ids: set[int] = set()

    route_stops = sorted(
        [stop for stop in (context.route_solution.stops or []) if getattr(stop, "order_id", None) is not None],
        key=lambda stop: stop.stop_order if getattr(stop, "stop_order", None) is not None else 0,
    )
    for stop in route_stops:
        order = order_by_id.get(stop.order_id)
        if not order or order.id in seen_order_ids:
            continue
        seen_order_ids.add(order.id)
        ordered.append(order)

    for order in context.orders:
        order_id = getattr(order, "id", None)
        if order_id is None or order_id in seen_order_ids:
            continue
        seen_order_ids.add(order_id)
        ordered.append(order)

    return ordered


def _resolve_order_service_duration_seconds(
    *,
    order,
    stop,
    service_durations: Dict[int, int],
    default_service_time: dict | None,
) -> int | None:
    service_duration_seconds = service_durations.get(order.id)
    if service_duration_seconds is not None:
        return service_duration_seconds

    effective_service_time = resolve_effective_service_time_payload(
        getattr(stop, "service_time", None),
        default_service_time,
    )
    service_duration_seconds = calculate_service_time_seconds(
        effective_service_time,
        resolve_order_item_quantity(order),
    )
    if service_duration_seconds is None and stop is not None:
        service_duration_seconds = parse_duration_seconds(
            getattr(stop, "service_duration", None),
        )
    return service_duration_seconds


def _location_group_key(location: Dict[str, float]) -> str:
    return (
        f"{float(location['latitude']):.6f},"
        f"{float(location['longitude']):.6f}"
    )


def _shipment_group_label(route_solution_id: int, location_key: str) -> str:
    return f"group:{route_solution_id}:{location_key}"


def _infer_location_from_orders(orders, stops=None, prefer: str = "lowest") -> Dict[str, Any]:
    if stops:
        target_stop = _select_stop_by_order(stops, prefer)
        if target_stop:
            order_lookup = {
                order.id: order for order in orders if getattr(order, "id", None) is not None
            }
            target_order = order_lookup.get(target_stop.order_id)
            if target_order and target_order.client_address:
                return target_order.client_address

    first = next((order for order in orders if order.client_address), None)
    if not first:
        raise ValidationFailed("Orders are missing client addresses for routing.")
    return first.client_address


def _select_stop_by_order(stops, prefer: str):
    eligible = [stop for stop in stops if stop.stop_order is not None]
    if not eligible:
        return None
    if prefer == "highest":
        return max(eligible, key=lambda stop: stop.stop_order)
    return min(eligible, key=lambda stop: stop.stop_order)


def _parse_service_durations(incoming_data: Dict[str, Any]) -> Dict[int, int]:
    raw = incoming_data.get("service_durations") or {}
    if not isinstance(raw, dict):
        return {}
    durations: Dict[int, int] = {}
    for key, value in raw.items():
        try:
            order_id = int(key)
        except (TypeError, ValueError):
            continue
        seconds = parse_duration_seconds(value)
        if seconds is not None:
            durations[order_id] = seconds
    return durations


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


def _combine_date_time(base: datetime, time_value: Optional[time_cls]) -> Optional[datetime]:
    if not time_value:
        return None
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return datetime.combine(base.date(), time_value, tzinfo=base.tzinfo)

def _resolve_global_time_bounds(
    context: OptimizationContext,
    incoming_data: Dict[str, Any],
) -> tuple[Optional[datetime], Optional[datetime]]:
    global_start = _coerce_datetime(incoming_data.get("global_start_time"))
    global_end = _coerce_datetime(incoming_data.get("global_end_time"))
    request_timezone = resolve_request_timezone(
        context.ctx,
        context.local_delivery_plan,
        identity=context.identity,
    )

    if global_start is None:
        global_start = _merge_plan_date_with_route_time(
            context.delivery_plan.start_date,
            context.route_solution.set_start_time,
            request_timezone=request_timezone,
            use_now_if_today=True,
        )

    if global_end is None:
        global_end = _merge_plan_date_with_route_time(
            context.delivery_plan.end_date,
            context.route_solution.set_end_time,
            request_timezone=request_timezone,
            use_now_if_today=False,
        )

    return global_start, global_end


def _merge_plan_date_with_route_time(
    plan_date_value: Any,
    time_value: Optional[str],
    *,
    request_timezone,
    use_now_if_today: bool,
) -> Optional[datetime]:
    base_date = _coerce_datetime(plan_date_value)
    if not base_date:
        return None

    parsed_time = _parse_time_string(time_value)
    if parsed_time:
        return combine_plan_date_and_local_hhmm_to_utc(
            plan_date=base_date,
            hhmm=time_value,
            tz=request_timezone,
        ) or base_date

    if use_now_if_today:
        now = datetime.now(tz=base_date.tzinfo or timezone.utc)
        if base_date.date() == now.date():
            return now

    return base_date


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

def _ensure_address_format(location: Dict[str, Any], label: str) -> None:
    if not isinstance(location, dict):
        raise ValidationFailed(f"{label} must be a JSON object.")
    if not location.get("street_address") or not location.get("country"):
        raise ValidationFailed(f"{label} must include street_address and country.")
    coordinates = location.get("coordinates")
    if not isinstance(coordinates, dict):
        raise ValidationFailed(f"{label} must include coordinates.")
    if coordinates.get("lat") is None or coordinates.get("lng") is None:
        raise ValidationFailed(f"{label} coordinates must include lat and lng.")

def _resolve_tz(*datetimes: Optional[datetime]) -> timezone:
    for dt in datetimes:
        if isinstance(dt, datetime) and dt.tzinfo is not None:
            return dt.tzinfo
    return timezone.utc
