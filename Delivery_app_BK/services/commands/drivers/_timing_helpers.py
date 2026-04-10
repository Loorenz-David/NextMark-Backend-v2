from __future__ import annotations

from datetime import datetime, timedelta

from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import resolve_actual_timestamp
from Delivery_app_BK.services.domain.route_operations.route_solution import RouteActualEndTimeSource

from ._helpers import is_within_route_window
from ._route_end_source import (
    ROUTE_END_SOURCE_EXPECTED,
    ROUTE_END_SOURCE_LAST_ORDER,
    ROUTE_END_SOURCE_MANUAL,
    get_driver_actual_end_time_source,
    set_driver_actual_end_time_source,
)

RouteEndSource = RouteActualEndTimeSource | str
TimingResultReason = str


def resolve_candidate_timestamp(observed_time: datetime | None) -> datetime:
    return resolve_actual_timestamp(observed_time)


def build_timing_result(
    *,
    recorded: bool,
    reason: TimingResultReason | None = None,
    route: dict | None = None,
    stop: dict | None = None,
):
    payload = {"recorded": recorded, "reason": reason}
    if route is not None:
        payload["route"] = route
    if stop is not None:
        payload["stop"] = stop
    return payload


def reject_outside_window(ctx: ServiceContext, message: str):
    ctx.set_warning(message)


def resolve_planned_remaining_travel_to_end_seconds(route_solution: RouteSolution) -> int:
    expected_end_time = getattr(route_solution, "expected_end_time", None)
    stops = getattr(route_solution, "stops", None) or []
    last_stop = stops[-1] if stops else None
    expected_departure_time = getattr(last_stop, "expected_departure_time", None)

    if expected_end_time is None or expected_departure_time is None:
        return 0

    delta = expected_end_time - expected_departure_time
    if not isinstance(delta, timedelta):
        return 0

    return max(0, int(delta.total_seconds()))


def mark_route_end_time(
    route_solution: RouteSolution,
    *,
    candidate_time: datetime,
    source: RouteEndSource,
):
    normalized_source = (
        source.value if isinstance(source, RouteActualEndTimeSource) else RouteActualEndTimeSource(source).value
    )
    current_source = get_driver_actual_end_time_source(route_solution)

    if normalized_source == ROUTE_END_SOURCE_EXPECTED:
        if route_solution.actual_end_time is not None:
            return False, "already_recorded"
    elif normalized_source == ROUTE_END_SOURCE_LAST_ORDER:
        if route_solution.actual_end_time is not None and current_source not in (None, ROUTE_END_SOURCE_EXPECTED):
            return False, "higher_priority_recorded"
    elif normalized_source == ROUTE_END_SOURCE_MANUAL:
        if route_solution.actual_end_time is not None and current_source == ROUTE_END_SOURCE_MANUAL:
            return False, "already_recorded"

    route_solution.actual_end_time = candidate_time
    set_driver_actual_end_time_source(route_solution, normalized_source)
    return True, None


def can_record_route_timestamp(route_solution: RouteSolution, candidate_time: datetime) -> bool:
    return is_within_route_window(route_solution, candidate_time)
