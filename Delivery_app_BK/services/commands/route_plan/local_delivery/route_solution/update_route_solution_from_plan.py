from __future__ import annotations

from datetime import datetime
import logging
from typing import Tuple

from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_PARTIAL,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    FULL_RECOMPUTE,
    refresh_local_delivery_route_execution,
    refresh_local_delivery_route_execution_instance,
)

from .clone import clone_route_solution
from .plan_sync.changes import apply_route_solution_field_updates
from .plan_sync.expectations import (
    apply_expected_end_shift_from_window,
    apply_expected_start_from_window,
    sync_route_end_warning,
)
from .plan_sync.stop_window_updates import apply_time_window_update
from .plan_sync.window import resolve_window, validate_window

logger = logging.getLogger(__name__)


def update_route_solution_from_plan(
    route_solution: RouteSolution,
    updates: dict | None,
    plan_start: datetime,
    plan_end: datetime,
    previous_plan_start: datetime | None = None,
    previous_plan_end: datetime | None = None,
    create_variant_on_save: bool = False,
    time_zone: str = None,
) -> Tuple[RouteSolution, bool, RouteSolution | None]:
    updates = updates or {}

    original_route_solution = None
    original_is_optimized = route_solution.is_optimized

    if create_variant_on_save:
        route_solution, _, original_route_solution = clone_route_solution(route_solution)
        if original_is_optimized == IS_OPTIMIZED_NOT_OPTIMIZED:
            route_solution.is_optimized = IS_OPTIMIZED_NOT_OPTIMIZED
            if original_route_solution is not None:
                original_route_solution.is_optimized = IS_OPTIMIZED_NOT_OPTIMIZED

    old_set_start_time = route_solution.set_start_time
    old_set_end_time = route_solution.set_end_time

    has_address_change, has_time_change, has_service_time_change = apply_route_solution_field_updates(
        route_solution=route_solution,
        updates=updates,
    )
    old_window = resolve_window(
        previous_plan_start or plan_start,
        previous_plan_end or plan_end,
        old_set_start_time,
        old_set_end_time,
        time_zone=time_zone,
    )
    new_window = resolve_window(
        plan_start,
        plan_end,
        route_solution.set_start_time,
        route_solution.set_end_time,
        time_zone=time_zone,
    )
   
    validate_window(new_window)

    window_changed = old_window != new_window
    stops_changed = original_route_solution is not None

    if has_address_change or has_service_time_change:
        if route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
            route_solution.is_optimized = IS_OPTIMIZED_PARTIAL

    if has_time_change and route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
        route_solution.is_optimized = IS_OPTIMIZED_PARTIAL

    if new_window and (window_changed or has_time_change):
        apply_expected_start_from_window(route_solution, new_window)

    if window_changed and new_window and old_window:
        shift_times = not has_address_change
        orders_by_id = _orders_by_id(route_solution)
        window_changes, has_violation = apply_time_window_update(
            route_solution,
            old_window,
            new_window,
            shift_times=shift_times,
            orders_by_id=orders_by_id,
        )
        stops_changed = stops_changed or window_changes
        apply_expected_end_shift_from_window(
            route_solution,
            old_window,
            new_window,
            shift_times,
        )
        if has_violation:
            route_solution.is_optimized = IS_OPTIMIZED_PARTIAL
    elif has_time_change and new_window:
        # Time text can change without changing parsed window boundaries.
        # Rebuild route-window warnings to keep stop-level violations current.
        orders_by_id = _orders_by_id(route_solution)
        warning_changes, has_violation = apply_time_window_update(
            route_solution,
            new_window,
            new_window,
            shift_times=False,
            orders_by_id=orders_by_id,
        )
        stops_changed = stops_changed or warning_changes
        if has_violation and route_solution.is_optimized != IS_OPTIMIZED_NOT_OPTIMIZED:
            route_solution.is_optimized = IS_OPTIMIZED_PARTIAL

    allowed_end = new_window[1] if new_window else None
    sync_route_end_warning(route_solution, allowed_end)

    requires_route_refresh = bool(
        any(getattr(stop, "order_id", None) for stop in (route_solution.stops or []))
        and (has_address_change or has_service_time_change or has_time_change or window_changed)
    )
    if requires_route_refresh:
        if route_solution.id is not None:
            route_solution, refreshed_stops = refresh_local_delivery_route_execution(
                route_solution.id,
                recompute_mode=FULL_RECOMPUTE,
                recompute_from_position=1,
                time_zone=time_zone,
            )
        else:
            route_solution, refreshed_stops = refresh_local_delivery_route_execution_instance(
                route_solution,
                recompute_mode=FULL_RECOMPUTE,
                recompute_from_position=1,
                time_zone=time_zone,
            )
        stops_changed = stops_changed or bool(refreshed_stops)
        logger.info(
            "Refreshed local-delivery route timings route_id=%s mode=%s",
            getattr(route_solution, "id", None),
            FULL_RECOMPUTE,
        )

    return route_solution, stops_changed, original_route_solution


def update_route_solution_from_route_plan(
    route_solution: RouteSolution,
    updates: dict | None,
    plan_start: datetime,
    plan_end: datetime,
    previous_plan_start: datetime | None = None,
    previous_plan_end: datetime | None = None,
    create_variant_on_save: bool = False,
    time_zone: str = None,
) -> Tuple[RouteSolution, bool, RouteSolution | None]:
    return update_route_solution_from_plan(
        route_solution=route_solution,
        updates=updates,
        plan_start=plan_start,
        plan_end=plan_end,
        previous_plan_start=previous_plan_start,
        previous_plan_end=previous_plan_end,
        create_variant_on_save=create_variant_on_save,
        time_zone=time_zone,
    )


def _orders_by_id(route_solution: RouteSolution) -> dict[int, object]:
    route_plan = None
    route_group = getattr(route_solution, "route_group", None)
    if route_group:
        route_plan = getattr(route_group, "route_plan", None)
    # Transitional fallback for legacy fixtures/doubles still using local_delivery_plan.
    if route_plan is None:
        legacy_group = getattr(route_solution, "local_delivery_plan", None)
        if legacy_group is not None:
            route_plan = getattr(legacy_group, "delivery_plan", None)
    if not route_plan:
        return {}
    return {
        order.id: order
        for order in (route_plan.orders or [])
        if getattr(order, "id", None) is not None
    }
