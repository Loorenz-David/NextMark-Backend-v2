from __future__ import annotations

from datetime import datetime, time as time_cls, timezone, timedelta
from typing import Dict, List, Optional

from Delivery_app_BK.models import Order, RouteSolution, RouteSolutionStop
from Delivery_app_BK.models.mixins.validation_mixins.time_warning_validation import (
    TimeWarningFactory,
)

from Delivery_app_BK.directions.domain.models import (
    DirectionsRequestBuildResult,
    DirectionsResult,
    DirectionsVisitGroup,
    DirectionsVisitStopMember,
)
from Delivery_app_BK.directions.services.request_builder import (
    _parse_time_string,
)
from Delivery_app_BK.directions.services.schedule_clamp import (
    apply_route_solution_schedule_clamp,
)
from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
    build_stop_time_warnings,
    ensure_utc,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    apply_expected_stop_schedule,
    clear_expected_stop_schedule,
    combine_plan_date_and_local_hhmm_to_utc,
    resolve_request_timezone,
)


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    return ensure_utc(value)


def apply_directions_result(
    route_solution: RouteSolution,
    directions_result: DirectionsResult,
    orders_by_id: Dict[int, Order],
    build_result: DirectionsRequestBuildResult,
) -> list[RouteSolutionStop]:
   
    if build_result.full_recompute:
        route_solution.total_distance_meters = directions_result.total_distance_meters
        route_solution.total_travel_time_seconds = directions_result.total_duration_seconds
        if directions_result.start_time is not None:
            route_solution.expected_start_time = _ensure_utc(directions_result.start_time)

    if directions_result.end_time is not None:
        route_solution.expected_end_time = _ensure_utc(directions_result.end_time)

    route_warnings: List[dict] = []
    allowed_end = _ensure_utc(_resolve_allowed_end(route_solution))
    end_time = _ensure_utc(directions_result.end_time)
    if allowed_end and end_time and end_time > allowed_end:
        route_warnings.append(
            TimeWarningFactory.route_end_time_exceeded(
                expected_end=end_time,
                allowed_end=allowed_end,
            )
        )
    route_solution.route_warnings = route_warnings or None
    route_solution.has_route_warnings = bool(route_warnings)

    anchor_stop, affected_stops = _resolve_scope_stops(route_solution, build_result)
    changed_stops: list[RouteSolutionStop] = []
    visit_groups = build_result.visit_groups or _fallback_visit_groups(affected_stops)
    resolved_groups = _resolve_group_stops(affected_stops, visit_groups)
    grouped_results = directions_result.stop_results

    for index, group_stops in enumerate(resolved_groups):
        if not group_stops:
            continue

        stop_result = grouped_results[index] if index < len(grouped_results) else None
        if stop_result is None:
            for stop in group_stops:
                _mark_stop_stale(stop)
                changed_stops.append(stop)
            continue

        current_arrival = _ensure_utc(stop_result.arrival_time)
        visit_group = visit_groups[index] if index < len(visit_groups) else None
        group_members = list(visit_group.members) if visit_group else []

        for member_index, stop in enumerate(group_stops):
            service_seconds = 0
            if member_index < len(group_members):
                service_seconds = int(group_members[member_index].service_duration_seconds or 0)
            apply_expected_stop_schedule(
                stop,
                expected_arrival_time=current_arrival,
                expected_service_duration_seconds=service_seconds,
            )
            stop.eta_status = "estimated"
            stop.in_range = True
            stop.reason_was_skipped = None

            order_instance = orders_by_id.get(stop.order_id) or getattr(stop, "order", None)
            apply_stop_time_window_evaluation(
                stop=stop,
                order=order_instance,
                route_solution=route_solution,
                arrival_time=stop.expected_arrival_time,
            )
            changed_stops.append(stop)

            if current_arrival is None:
                continue

            current_arrival = stop.expected_departure_time

    changed_stops.extend(
        _apply_segment_polylines(
            route_solution=route_solution,
            leg_polylines=directions_result.leg_polylines,
            full_recompute=build_result.full_recompute,
            anchor_stop=anchor_stop,
            visit_groups=resolved_groups,
        )
    )

    clamped_stops, _ = apply_route_solution_schedule_clamp(
        route_solution=route_solution,
        grouped_stops=resolved_groups,
        orders_by_id=orders_by_id,
        base_end_time=end_time,
    )
    changed_stops.extend(clamped_stops)

    return _dedupe_stops(changed_stops)


def _resolve_scope_stops(
    route_solution: RouteSolution,
    build_result: DirectionsRequestBuildResult,
) -> tuple[RouteSolutionStop | None, list[RouteSolutionStop]]:
    ordered_stops = sorted(
        [stop for stop in (route_solution.stops or []) if stop.order_id],
        key=lambda stop: stop.stop_order if stop.stop_order is not None else 0,
    )
    if build_result.full_recompute:
        return None, ordered_stops

    anchor_stop = None
    anchor_position = build_result.effective_start_position - 1
    if anchor_position >= 1:
        for stop in ordered_stops:
            if (stop.stop_order or 0) == anchor_position:
                anchor_stop = stop
                break

    affected_stops = [
        stop
        for stop in ordered_stops
        if (stop.stop_order or 0) >= build_result.effective_start_position
    ]

    return anchor_stop, affected_stops


def _apply_segment_polylines(
    route_solution: RouteSolution,
    leg_polylines: list[Optional[str]],
    full_recompute: bool,
    anchor_stop: RouteSolutionStop | None,
    visit_groups: list[list[RouteSolutionStop]],
) -> list[RouteSolutionStop]:
    changed: list[RouteSolutionStop] = []

    def _leg(index: int) -> Optional[str]:
        if 0 <= index < len(leg_polylines):
            return leg_polylines[index]
        return None

    if full_recompute:
        route_solution.start_leg_polyline = _leg(0)

    if full_recompute:
        for index, group_stops in enumerate(visit_groups):
            outbound_polyline = _leg(index + 1) if index + 1 < len(visit_groups) else None
            changed.extend(_apply_group_polyline(group_stops, outbound_polyline))
        route_solution.end_leg_polyline = _leg(len(visit_groups))
        return changed

    if anchor_stop is None:
        return changed

    if not visit_groups:
        anchor_stop.to_next_polyline = None
        route_solution.end_leg_polyline = _leg(0)
        changed.append(anchor_stop)
        return changed

    anchor_stop.to_next_polyline = _leg(0)
    changed.append(anchor_stop)

    for index, group_stops in enumerate(visit_groups):
        outbound_polyline = _leg(index + 1) if index + 1 < len(visit_groups) else None
        changed.extend(_apply_group_polyline(group_stops, outbound_polyline))

    route_solution.end_leg_polyline = _leg(len(visit_groups))
    return changed


def _apply_group_polyline(
    group_stops: list[RouteSolutionStop],
    outbound_polyline: Optional[str],
) -> list[RouteSolutionStop]:
    changed: list[RouteSolutionStop] = []
    if not group_stops:
        return changed

    last_index = len(group_stops) - 1
    for index, stop in enumerate(group_stops):
        stop.to_next_polyline = outbound_polyline if index == last_index else None
        changed.append(stop)
    return changed


def _dedupe_stops(stops: list[RouteSolutionStop]) -> list[RouteSolutionStop]:
    deduped: list[RouteSolutionStop] = []
    seen: set[int] = set()
    for stop in stops:
        stop_id = getattr(stop, "id", None)
        if stop_id in seen:
            continue
        if stop_id is not None:
            seen.add(stop_id)
        deduped.append(stop)
    return deduped


def _resolve_group_stops(
    affected_stops: list[RouteSolutionStop],
    visit_groups: list[DirectionsVisitGroup],
) -> list[list[RouteSolutionStop]]:
    stop_by_id = {
        stop.id: stop
        for stop in affected_stops
        if getattr(stop, "id", None) is not None
    }
    unused_by_order_id = {
        stop.order_id: stop
        for stop in affected_stops
        if getattr(stop, "order_id", None) is not None
    }

    resolved: list[list[RouteSolutionStop]] = []
    for group in visit_groups:
        group_stops: list[RouteSolutionStop] = []
        for member in group.members:
            stop = None
            if member.stop_id is not None:
                stop = stop_by_id.pop(member.stop_id, None)
            if stop is None and member.order_id is not None:
                stop = unused_by_order_id.pop(member.order_id, None)
            if stop is not None:
                if getattr(stop, "id", None) is not None:
                    stop_by_id.pop(stop.id, None)
                if getattr(stop, "order_id", None) is not None:
                    unused_by_order_id.pop(stop.order_id, None)
                group_stops.append(stop)
        resolved.append(group_stops)
    return resolved


def _fallback_visit_groups(
    affected_stops: list[RouteSolutionStop],
) -> list[DirectionsVisitGroup]:
    fallback: list[DirectionsVisitGroup] = []
    for stop in affected_stops:
        if not getattr(stop, "order_id", None):
            continue
        fallback.append(
            DirectionsVisitGroup(
                location={},
                location_key=str(getattr(stop, "id", getattr(stop, "order_id", ""))),
                members=[
                    DirectionsVisitStopMember(
                        stop_id=getattr(stop, "id", None),
                        order_id=stop.order_id,
                        service_duration_seconds=0,
                    )
                ],
            )
        )
    return fallback


def _mark_stop_stale(stop: RouteSolutionStop) -> None:
    clear_expected_stop_schedule(stop)
    stop.eta_status = "stale"
    stop.has_constraint_violation = False
    stop.constraint_warnings = None
    stop.in_range = False
    stop.reason_was_skipped = "Route timing unavailable"

def _resolve_allowed_end(route_solution: RouteSolution) -> Optional[datetime]:
    route_group = getattr(route_solution, "route_group", None)
    if route_group is None:
        return None
    route_plan = getattr(route_group, "route_plan", None)
    if not route_plan or not route_plan.end_date:
        return None
    request_timezone = resolve_request_timezone(
        plan_instance=route_group,
    )

    if route_solution.set_end_time:
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


def _build_stop_warnings(
    order: Optional[Order],
    arrival_time: Optional[datetime],
    route_solution: RouteSolution,
) -> List[dict]:
    return build_stop_time_warnings(order, arrival_time, route_solution)
