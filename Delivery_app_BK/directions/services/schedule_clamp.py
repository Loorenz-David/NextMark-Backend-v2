from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from Delivery_app_BK.models import Order, RouteSolution, RouteSolutionStop
from Delivery_app_BK.models.mixins.validation_mixins.time_warning_validation import (
    TimeWarningFactory,
)

from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
    build_effective_windows,
    ensure_utc,
    resolve_next_window_start,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    apply_expected_stop_schedule,
    combine_plan_date_and_local_hhmm_to_utc,
    resolve_request_timezone,
)


def group_contiguous_route_stops(
    stops: list[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
) -> list[list[RouteSolutionStop]]:
    grouped: list[list[RouteSolutionStop]] = []

    for stop in stops or []:
        order = orders_by_id.get(getattr(stop, "order_id", None)) or getattr(stop, "order", None)
        location_key = _location_group_key(order)
        if grouped and location_key is not None and location_key == _location_group_key_for_group(grouped[-1], orders_by_id):
            grouped[-1].append(stop)
            continue
        grouped.append([stop])

    return grouped


def apply_route_solution_schedule_clamp(
    *,
    route_solution: RouteSolution,
    grouped_stops: list[list[RouteSolutionStop]],
    orders_by_id: Dict[int, Order],
    base_end_time: Optional[datetime],
) -> tuple[list[RouteSolutionStop], bool]:
    changed: list[RouteSolutionStop] = []
    accumulated_shift = timedelta(0)

    for group_stops in grouped_stops:
        if not group_stops:
            continue

        additional_shift = _resolve_group_additional_shift(
            group_stops=group_stops,
            route_solution=route_solution,
            orders_by_id=orders_by_id,
            accumulated_shift=accumulated_shift,
        )
        accumulated_shift += additional_shift

        for stop in group_stops:
            previous_state = _snapshot_stop_state(stop)
            raw_arrival = ensure_utc(getattr(stop, "expected_arrival_time", None))
            if raw_arrival is None:
                order_instance = orders_by_id.get(stop.order_id) or getattr(stop, "order", None)
                apply_stop_time_window_evaluation(
                    stop=stop,
                    order=order_instance,
                    route_solution=route_solution,
                    arrival_time=None,
                )
            else:
                raw_departure = ensure_utc(getattr(stop, "expected_departure_time", None)) or raw_arrival
                final_arrival = raw_arrival + accumulated_shift
                final_departure = raw_departure + accumulated_shift
                service_seconds = int(
                    max(
                        0,
                        (final_departure - final_arrival).total_seconds(),
                    )
                )
                apply_expected_stop_schedule(
                    stop,
                    expected_arrival_time=final_arrival,
                    expected_service_duration_seconds=service_seconds,
                )
                order_instance = orders_by_id.get(stop.order_id) or getattr(stop, "order", None)
                apply_stop_time_window_evaluation(
                    stop=stop,
                    order=order_instance,
                    route_solution=route_solution,
                    arrival_time=final_arrival,
                )

            if _snapshot_stop_state(stop) != previous_state:
                changed.append(stop)

    previous_route_state = _snapshot_route_state(route_solution)
    final_end_time = base_end_time + accumulated_shift if base_end_time is not None else None
    route_solution.expected_end_time = final_end_time
    _apply_route_end_warnings(route_solution, final_end_time)
    route_changed = _snapshot_route_state(route_solution) != previous_route_state

    return changed, route_changed


def _resolve_group_additional_shift(
    *,
    group_stops: list[RouteSolutionStop],
    route_solution: RouteSolution,
    orders_by_id: Dict[int, Order],
    accumulated_shift: timedelta,
) -> timedelta:
    group_shift = timedelta(0)

    while True:
        updated = False
        for stop in group_stops:
            order_instance = orders_by_id.get(stop.order_id) or getattr(stop, "order", None)
            if order_instance is None:
                continue

            windows = build_effective_windows(order_instance, route_solution)
            raw_arrival = ensure_utc(getattr(stop, "expected_arrival_time", None))
            if raw_arrival is None:
                continue

            effective_arrival = raw_arrival + accumulated_shift + group_shift
            next_window_start = resolve_next_window_start(effective_arrival, windows)
            if next_window_start is None:
                continue

            candidate_shift = next_window_start - raw_arrival - accumulated_shift
            if candidate_shift > group_shift:
                group_shift = candidate_shift
                updated = True

        if not updated:
            return group_shift


def _apply_route_end_warnings(
    route_solution: RouteSolution,
    end_time: Optional[datetime],
) -> None:
    route_warnings: list[dict] = []
    allowed_end = ensure_utc(_resolve_allowed_end(route_solution))
    resolved_end_time = ensure_utc(end_time)
    if allowed_end and resolved_end_time and resolved_end_time > allowed_end:
        route_warnings.append(
            TimeWarningFactory.route_end_time_exceeded(
                expected_end=resolved_end_time,
                allowed_end=allowed_end,
            )
        )
    route_solution.route_warnings = route_warnings or None
    route_solution.has_route_warnings = bool(route_warnings)


def _resolve_allowed_end(route_solution: RouteSolution) -> Optional[datetime]:
    route_group = getattr(route_solution, "route_group", None)
    if route_group is None:
        return None
    route_plan = getattr(route_group, "route_plan", None)
    if not route_plan:
        return None

    request_timezone = resolve_request_timezone(plan_instance=route_group)
    if getattr(route_solution, "set_end_time", None):
        parsed = _parse_time_string(route_solution.set_end_time)
        if parsed:
            return combine_plan_date_and_local_hhmm_to_utc(
                plan_date=route_plan.end_date,
                hhmm=route_solution.set_end_time,
                tz=request_timezone,
            )

    return combine_plan_date_and_local_hhmm_to_utc(
        plan_date=route_plan.end_date,
        hhmm="23:59:59",
        tz=request_timezone,
    )


def _location_group_key(order: Optional[Order]) -> str | None:
    if order is None:
        return None
    address = getattr(order, "client_address", None) or {}
    coordinates = address.get("coordinates", address) if isinstance(address, dict) else {}
    lat = coordinates.get("lat") or coordinates.get("latitude")
    lng = coordinates.get("lng") or coordinates.get("longitude")
    if lat is None or lng is None:
        return None
    return f"{float(lat):.6f},{float(lng):.6f}"


def _location_group_key_for_group(
    group_stops: list[RouteSolutionStop],
    orders_by_id: Dict[int, Order],
) -> str | None:
    first = group_stops[0] if group_stops else None
    if first is None:
        return None
    order = orders_by_id.get(getattr(first, "order_id", None)) or getattr(first, "order", None)
    return _location_group_key(order)


def _snapshot_stop_state(stop: RouteSolutionStop) -> tuple:
    return (
        ensure_utc(getattr(stop, "expected_arrival_time", None)),
        ensure_utc(getattr(stop, "expected_departure_time", None)),
        getattr(stop, "expected_service_duration_seconds", None),
        bool(getattr(stop, "has_constraint_violation", False)),
        getattr(stop, "constraint_warnings", None),
        getattr(stop, "reason_was_skipped", None),
        getattr(stop, "in_range", None),
    )


def _snapshot_route_state(route_solution: RouteSolution) -> tuple:
    return (
        ensure_utc(getattr(route_solution, "expected_end_time", None)),
        bool(getattr(route_solution, "has_route_warnings", False)),
        getattr(route_solution, "route_warnings", None),
    )


def _parse_time_string(value: Optional[str]):
    if not value:
        return None
    parts = str(value).strip().split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return (hour, minute, second)
