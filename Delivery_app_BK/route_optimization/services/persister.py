from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_OPTIMIZE,
)
from Delivery_app_BK.route_optimization.constants.skip_reason_messages import (
    resolve_skip_reason_message,
)
from Delivery_app_BK.route_optimization.constants.skip_reasons import (
    OUTSIDE_OPTIMIZATION_WINDOW,
)

from Delivery_app_BK.models import RouteSolutionStop, RouteSolution,db
from Delivery_app_BK.models.mixins.validation_mixins.time_warning_validation import (
    TimeWarningFactory,
)
from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
from Delivery_app_BK.services.domain.vehicle.apply_vehicle_warnings import (
    apply_vehicle_warnings_to_route_solution,
)
from Delivery_app_BK.route_optimization.domain.models import (
    OptimizationContext,
    OptimizationRequest,
    OptimizationResult,
    Shipment,
)
from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    apply_expected_stop_schedule,
    clear_expected_stop_schedule,
)
from Delivery_app_BK.services.commands.utils import generate_client_id


def persist_solution(
    context: OptimizationContext,
    request: OptimizationRequest,
    result: OptimizationResult,
    provider_name: str,
) -> Dict[str, Any]:
    route_solution = context.route_solution
    route_solution.algorithm = provider_name
    route_solution.score = calculate_score(result)
    route_solution.total_distance_meters = result.total_distance_meters
    route_solution.total_travel_time_seconds = result.total_duration_seconds
    route_solution.expected_start_time = _parse_datetime(result.expected_start_time)
    route_solution.expected_end_time = _parse_datetime(result.expected_end_time)
    route_solution.start_leg_polyline = None
    route_solution.end_leg_polyline = None

    route_solution.start_location = request.start_location
    route_solution.end_location = request.end_location
    
    route_solution.is_optimized = IS_OPTIMIZED_OPTIMIZE
    route_solution.has_route_warnings = False
    route_solution.route_warnings = None

    stop_lookup = {stop.order_id: stop for stop in (route_solution.stops or [])}
    _temporarily_displace_existing_stop_orders(route_solution, stop_lookup.values())
    shipment_lookup = {
        shipment.label: shipment
        for shipment in [*(request.shipments or []), *(request.excluded_shipments or [])]
    }
    orders_by_id = {
        order.id: order for order in context.orders if getattr(order, "id", None) is not None
    }
    stop_payloads: List[Dict[str, Any]] = []
    skipped_payloads: List[Dict[str, Any]] = []
    payload_refs: List[tuple[Dict[str, Any], RouteSolutionStop]] = []
    routed_stop_groups: list[list[RouteSolutionStop]] = []
    next_stop_order = 1

    for grouped_stop in result.stops:
        shipment = shipment_lookup.get(grouped_stop.shipment_label)
        if shipment is None:
            continue

        group_instances: list[RouteSolutionStop] = []
        current_arrival = _parse_datetime(grouped_stop.expected_arrival_time)
        for member in shipment.members:
            order_id = member.order_id
            stop_instance = _ensure_route_stop_instance(
                stop_lookup=stop_lookup,
                route_solution=route_solution,
                order_id=order_id,
                team_id=context.route_group.team_id,
            )
            stop_instance.stop_order = next_stop_order
            service_seconds = int(member.service_duration_seconds or 0)
            apply_expected_stop_schedule(
                stop_instance,
                expected_arrival_time=current_arrival,
                expected_service_duration_seconds=service_seconds,
            )
            stop_instance.in_range = grouped_stop.in_range
            stop_instance.reason_was_skipped = None
            stop_instance.eta_status = "valid"
            stop_instance.has_constraint_violation = False
            stop_instance.constraint_warnings = None
            stop_instance.to_next_polyline = None
            _apply_stop_time_warnings(
                stop_instance=stop_instance,
                route_solution=route_solution,
                order_instance=orders_by_id.get(order_id),
            )
            group_instances.append(stop_instance)
            payload = _build_stop_payload(stop_instance, route_solution.id)
            stop_payloads.append(payload)
            payload_refs.append((payload, stop_instance))
            next_stop_order += 1

            if current_arrival is not None:
                current_arrival = stop_instance.expected_departure_time

        if group_instances:
            routed_stop_groups.append(group_instances)

    last_stop_order = max(
        (p["stop_order"] for p in stop_payloads),
        default=0,
    )

    skipped_index = 0
    all_skipped = [*(request.pre_skipped_shipments or []), *(result.skipped or [])]
    for skipped in all_skipped:
        shipment = shipment_lookup.get(skipped.shipment_label)
        if shipment is None:
            continue

        for member in shipment.members:
            stop_instance = _ensure_route_stop_instance(
                stop_lookup=stop_lookup,
                route_solution=route_solution,
                order_id=member.order_id,
                team_id=context.route_group.team_id,
            )
            stop_instance.in_range = False
            clear_expected_stop_schedule(stop_instance)
            stop_instance.reason_was_skipped = resolve_skip_reason_message(skipped.reason)
            stop_instance.eta_status = "stale"
            stop_instance.has_constraint_violation = False
            stop_instance.constraint_warnings = None
            stop_instance.to_next_polyline = None
            stop_instance.stop_order = last_stop_order + skipped_index + 1
            _apply_pre_skipped_window_violation(
                stop_instance=stop_instance,
                skipped_reason=skipped.reason,
                request=request,
            )
            skipped_index += 1
            payload = _build_stop_payload(stop_instance, route_solution.id)
            skipped_payloads.append(payload)
            payload_refs.append((payload, stop_instance))



    if request.populate_transition_polylines:
        _assign_segment_polylines(
            route_solution=route_solution,
            routed_stop_groups=routed_stop_groups,
            transition_polylines=result.transition_polylines or [],
        )

    # Apply vehicle warnings after distance/duration are finalised on the
    # route_solution.  route_warnings was reset to None at the top of this
    # function so we start from a clean slate — no stale vehicle entries.
    _opt_vehicle = (
        db.session.get(Vehicle, route_solution.vehicle_id)
        if getattr(route_solution, "vehicle_id", None)
        else None
    )
    apply_vehicle_warnings_to_route_solution(
        route_solution,
        _opt_vehicle,
        orders=list(context.orders),
        flush=False,
    )

    db.session.add(route_solution)
    db.session.flush()

    for payload, stop_instance in payload_refs:
        payload["id"] = stop_instance.id
        payload["to_next_polyline"] = stop_instance.to_next_polyline

    db.session.commit()

    if context.return_shape == "map_ids_object":
        route_solution_payload = _build_route_solution_payload(route_solution)
        return {
            "route_solution": {
                route_solution.client_id: route_solution_payload,
            },
            "route_solution_stop": {
                payload["client_id"]: payload for payload in stop_payloads
            },
            "route_solution_stop_skipped": {
                payload["client_id"]: payload for payload in skipped_payloads
            },
        }

    return {
        "route_solution": {},
        "route_solution_stop": [],
        "route_solution_id": route_solution.id,
        "total_distance_meters": result.total_distance_meters,
        "total_duration_seconds": result.total_duration_seconds,
        "expected_start_time": result.expected_start_time,
        "expected_end_time": result.expected_end_time,
        "stops": stop_payloads,
        "skipped": skipped_payloads,
    }


def _build_route_solution_payload(route_solution:RouteSolution) -> Dict[str, Any]:
    return {
        "id": route_solution.id,
        "client_id": route_solution.client_id,
        "_representation": "full",
        "label": route_solution.label,
        "is_selected": route_solution.is_selected,
        "is_optimized": route_solution.is_optimized,
        "stop_count": len(route_solution.stops or []),
        "total_distance_meters": route_solution.total_distance_meters,
        "total_travel_time_seconds": route_solution.total_travel_time_seconds,
        "expected_start_time": _serialize_datetime(route_solution.expected_start_time),
        "expected_end_time": _serialize_datetime(route_solution.expected_end_time),
        "start_leg_polyline": route_solution.start_leg_polyline,
        "end_leg_polyline": route_solution.end_leg_polyline,
        "start_location": route_solution.start_location,
        "end_location": route_solution.end_location,
        "set_start_time": route_solution.set_start_time,
        "set_end_time": route_solution.set_end_time,
        "eta_message_tolerance": route_solution.eta_message_tolerance if route_solution.eta_message_tolerance is not None else 1800,
        "stops_service_time": route_solution.stops_service_time,
        "driver_id": route_solution.driver_id,
        "route_group_id": route_solution.route_group_id,
        "has_route_warnings": route_solution.has_route_warnings,
        "route_warnings": route_solution.route_warnings,
    }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(parsed)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _assign_segment_polylines(
    route_solution: RouteSolution,
    routed_stop_groups: list[list[RouteSolutionStop]],
    transition_polylines: list[Optional[str]],
) -> None:
    if not transition_polylines:
        route_solution.start_leg_polyline = None
        route_solution.end_leg_polyline = None
        for group in routed_stop_groups:
            for stop in group:
                stop.to_next_polyline = None
        return

    route_solution.start_leg_polyline = transition_polylines[0] if transition_polylines else None
    route_solution.end_leg_polyline = (
        transition_polylines[len(routed_stop_groups)]
        if len(transition_polylines) > len(routed_stop_groups)
        else None
    )

    for idx, group in enumerate(routed_stop_groups):
        outbound_polyline = (
            transition_polylines[idx + 1]
            if idx + 1 < len(routed_stop_groups)
            and len(transition_polylines) > (idx + 1)
            else None
        )
        _assign_group_polyline(group, outbound_polyline)


def calculate_score(result:OptimizationResult):
    
    score = (
        result.total_distance_meters
        + 60 * result.total_duration_seconds
        + 10_000 * len(result.skipped)
    )

    return score


def _ensure_route_stop_instance(
    *,
    stop_lookup: dict[int, RouteSolutionStop],
    route_solution: RouteSolution,
    order_id: int,
    team_id: int,
) -> RouteSolutionStop:
    stop_instance = stop_lookup.get(order_id)
    if not stop_instance:
        stop_instance = RouteSolutionStop(
            client_id=generate_client_id('route_stop'),
            route_solution_id=route_solution.id,
            order_id=order_id,
            team_id=team_id,
        )
        route_solution.stops.append(stop_instance)
        db.session.add(stop_instance)
        stop_lookup[order_id] = stop_instance
    if not stop_instance.client_id:
        stop_instance.client_id = generate_client_id('route_stop')
    return stop_instance


def _temporarily_displace_existing_stop_orders(
    route_solution: RouteSolution,
    stops,
) -> None:
    persisted_stops = [
        stop
        for stop in stops
        if getattr(stop, "id", None) is not None and getattr(stop, "stop_order", None) is not None
    ]
    if not persisted_stops:
        return

    current_max = max(
        (int(getattr(stop, "stop_order", 0) or 0) for stop in persisted_stops),
        default=0,
    )
    temp_base = current_max + len(persisted_stops) + 1000

    for index, stop in enumerate(
        sorted(
            persisted_stops,
            key=lambda candidate: (
                int(getattr(candidate, "stop_order", 0) or 0),
                int(getattr(candidate, "id", 0) or 0),
            ),
        ),
        start=1,
    ):
        stop.stop_order = temp_base + index

    db.session.add(route_solution)
    db.session.flush()


def _build_stop_payload(
    stop_instance: RouteSolutionStop,
    route_solution_id: int,
) -> Dict[str, Any]:
    return {
        "id": stop_instance.id,
        "client_id": stop_instance.client_id,
        "order_id": stop_instance.order_id,
        "stop_order": stop_instance.stop_order,
        "service_time": stop_instance.service_time,
        "expected_arrival_time": _serialize_datetime(stop_instance.expected_arrival_time),
        "expected_departure_time": _serialize_datetime(stop_instance.expected_departure_time),
        "expected_service_duration_seconds": stop_instance.expected_service_duration_seconds,
        "in_range": stop_instance.in_range,
        "eta_status": stop_instance.eta_status,
        "reason_was_skipped": stop_instance.reason_was_skipped,
        "route_solution_id": route_solution_id,
        "has_constraint_violation": stop_instance.has_constraint_violation,
        "constraint_warnings": stop_instance.constraint_warnings,
        "to_next_polyline": stop_instance.to_next_polyline,
    }


def _assign_group_polyline(
    group: list[RouteSolutionStop],
    outbound_polyline: Optional[str],
) -> None:
    if not group:
        return
    last_index = len(group) - 1
    for index, stop in enumerate(group):
        stop.to_next_polyline = outbound_polyline if index == last_index else None


def _apply_stop_time_warnings(
    *,
    stop_instance: RouteSolutionStop,
    route_solution: RouteSolution,
    order_instance,
) -> None:
    if order_instance is None:
        return
    apply_stop_time_window_evaluation(
        stop=stop_instance,
        order=order_instance,
        route_solution=route_solution,
        arrival_time=stop_instance.expected_arrival_time,
    )


def _apply_pre_skipped_window_violation(
    *,
    stop_instance: RouteSolutionStop,
    skipped_reason,
    request: OptimizationRequest,
) -> None:
    if skipped_reason != OUTSIDE_OPTIMIZATION_WINDOW:
        return
    shipment = next(
        (
            candidate
            for candidate in (request.excluded_shipments or [])
            if any(member.order_id == stop_instance.order_id for member in candidate.members)
        ),
        None,
    )
    reference_window = _pick_reference_time_window(
        shipment.time_windows if shipment is not None else [],
        global_start_time=request.global_start_time,
        global_end_time=request.global_end_time,
    )
    if reference_window is None:
        return
    stop_instance.constraint_warnings = [
        TimeWarningFactory.optimization_window_excluded(
            allowed_start=reference_window[0],
            allowed_end=reference_window[1],
        )
    ]
    stop_instance.has_constraint_violation = True


def _pick_reference_time_window(
    windows,
    *,
    global_start_time: datetime | None,
    global_end_time: datetime | None,
) -> tuple[datetime, datetime] | None:
    normalized = [
        (window.start_time, window.end_time)
        for window in (windows or [])
        if getattr(window, "start_time", None) is not None
        and getattr(window, "end_time", None) is not None
    ]
    if not normalized:
        return None

    if global_start_time is None and global_end_time is None:
        return normalized[0]

    horizon_start = global_start_time or global_end_time
    horizon_end = global_end_time or global_start_time
    if horizon_start is None or horizon_end is None:
        return normalized[0]

    def _distance(window: tuple[datetime, datetime]) -> float:
        window_start, window_end = window
        if window_end <= horizon_start:
            return (horizon_start - window_end).total_seconds()
        if window_start >= horizon_end:
            return (window_start - horizon_end).total_seconds()
        return 0.0

    return min(normalized, key=_distance)
