from datetime import datetime
from typing import Any, Optional, Tuple

from Delivery_app_BK.directions.services.time_window_policy import (
    apply_stop_time_window_evaluation,
    apply_stop_time_window_evaluation_for_windows,
)
from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    apply_expected_stop_schedule,
    clear_expected_stop_schedule,
    resolve_expected_service_duration_seconds,
    resolve_order_item_quantity,
)
from .normalizers import ensure_utc


def apply_time_window_update(
    route_solution: RouteSolution,
    old_window: Tuple[datetime, datetime],
    new_window: Tuple[datetime, datetime],
    shift_times: bool,
    orders_by_id: Optional[dict[int, Any]] = None,
) -> Tuple[bool, bool]:
    old_start, _ = old_window
    new_start, new_end = new_window
    old_start = ensure_utc(old_start)
    new_start = ensure_utc(new_start)
    new_end = ensure_utc(new_end)
  
    shift_delta = None
    if shift_times and new_start and old_start and new_start != old_start:
        shift_delta = new_start - old_start
   
    has_updates = False
    has_violation = False

    for stop in route_solution.stops or []:
        arrival = ensure_utc(stop.expected_arrival_time)
        if arrival:
            order_instance = None
            if getattr(stop, "order_id", None) is not None and orders_by_id:
                order_instance = orders_by_id.get(stop.order_id)
            if order_instance is None:
                order_instance = getattr(stop, "order", None)

            expected_service_duration_seconds = resolve_expected_service_duration_seconds(
                stop_service_time=getattr(stop, "service_time", None),
                route_solution_service_time=getattr(route_solution, "stops_service_time", None),
                item_quantity=resolve_order_item_quantity(order_instance) if order_instance is not None else 0,
                legacy_service_duration=getattr(stop, "service_duration", None),
            )
            apply_expected_stop_schedule(
                stop,
                expected_arrival_time=arrival,
                expected_service_duration_seconds=expected_service_duration_seconds,
            )
        else:
            clear_expected_stop_schedule(stop)
        if shift_delta and arrival:
            shifted_arrival = arrival + shift_delta
            apply_expected_stop_schedule(
                stop,
                expected_arrival_time=shifted_arrival,
                expected_service_duration_seconds=getattr(stop, "expected_service_duration_seconds", None),
            )
            stop.eta_status = "estimated"
            arrival = stop.expected_arrival_time
            has_updates = True

        order_instance = None
        if getattr(stop, "order_id", None) is not None and orders_by_id:
            order_instance = orders_by_id.get(stop.order_id)
        if order_instance is None:
            order_instance = getattr(stop, "order", None)

        if order_instance is not None:
            state_changed = apply_stop_time_window_evaluation(
                stop=stop,
                order=order_instance,
                route_solution=route_solution,
                arrival_time=arrival,
            )
        else:
            state_changed = apply_stop_time_window_evaluation_for_windows(
                stop=stop,
                arrival_time=arrival,
                windows=[(new_start, new_end)],
            )
        if state_changed:
            has_updates = True
            if stop.has_constraint_violation:
                has_violation = True

    return has_updates, has_violation
