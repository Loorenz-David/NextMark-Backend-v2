from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from Delivery_app_BK.directions import refresh_route_solution_incremental
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan, RouteGroup, RouteSolution, RouteSolutionStop, db

logger = logging.getLogger(__name__)

FULL_RECOMPUTE = "full"
INCREMENTAL_RECOMPUTE = "incremental"


def ensure_single_selected_route_solution(
    route_group_id: int | None,
    *,
    preferred_route_solution_id: int | None = None,
) -> list[RouteSolution]:
    if route_group_id is None:
        return []

    route_solutions = (
        db.session.query(RouteSolution)
        .filter(RouteSolution.route_group_id == route_group_id)
        .order_by(RouteSolution.id.asc())
        .with_for_update()
        .all()
    )
    if not route_solutions:
        return []

    preferred_route = None
    if preferred_route_solution_id is not None:
        preferred_route = next(
            (
                route_solution
                for route_solution in route_solutions
                if route_solution.id == preferred_route_solution_id
            ),
            None,
        )

    selected_route = preferred_route or next(
        (route_solution for route_solution in route_solutions if route_solution.is_selected),
        None,
    )
    if selected_route is None:
        selected_route = route_solutions[0]

    updated_routes: list[RouteSolution] = []
    for route_solution in route_solutions:
        next_selected = route_solution.id == selected_route.id
        if route_solution.is_selected == next_selected:
            continue
        route_solution.is_selected = next_selected
        updated_routes.append(route_solution)

    if selected_route.id is not None and selected_route not in updated_routes and not selected_route.is_selected:
        selected_route.is_selected = True
        updated_routes.append(selected_route)

    return updated_routes


def lock_route_solution(route_solution_id: int | None) -> RouteSolution | None:
    if route_solution_id is None:
        return None

    return (
        db.session.query(RouteSolution)
        .filter(RouteSolution.id == route_solution_id)
        .with_for_update()
        .one_or_none()
    )


def get_next_route_stop_order(route_solution_id: int | None) -> int:
    if route_solution_id is None:
        return 1

    last_order = (
        db.session.query(RouteSolutionStop.stop_order)
        .filter(RouteSolutionStop.route_solution_id == route_solution_id)
        .order_by(RouteSolutionStop.stop_order.desc(), RouteSolutionStop.id.desc())
        .with_for_update()
        .first()
    )
    current_max = last_order[0] if last_order and last_order[0] is not None else 0
    return current_max + 1


def normalize_route_solution_stop_ordering(
    route_solution: RouteSolution | None,
) -> tuple[list[RouteSolutionStop], int | None]:
    if route_solution is None:
        return [], None

    ordered_stops = sorted(
        list(route_solution.stops or []),
        key=lambda stop: (
            stop.stop_order if stop.stop_order is not None else 10**9,
            getattr(stop, "id", 10**9),
            getattr(stop, "client_id", ""),
        ),
    )

    changed_stops: list[RouteSolutionStop] = []
    first_changed_position: int | None = None
    for index, stop in enumerate(ordered_stops, start=1):
        if stop.stop_order == index:
            continue
        previous_order = stop.stop_order
        stop.stop_order = index
        changed_stops.append(stop)
        candidate_position = previous_order if previous_order is not None else index
        if first_changed_position is None:
            first_changed_position = candidate_position
        else:
            first_changed_position = min(first_changed_position, candidate_position)

    return changed_stops, first_changed_position


def refresh_local_delivery_route_execution(
    route_solution_id: int | None,
    *,
    recompute_mode: str = INCREMENTAL_RECOMPUTE,
    recompute_from_position: int = 1,
    time_zone: str | None = None,
    warning_sink=None,
) -> tuple[RouteSolution | None, list[RouteSolutionStop]]:
    route_solution = load_route_solution_for_refresh(route_solution_id)
    if route_solution is None:
        return None, []

    return refresh_local_delivery_route_execution_instance(
        route_solution,
        recompute_mode=recompute_mode,
        recompute_from_position=recompute_from_position,
        time_zone=time_zone,
        warning_sink=warning_sink,
    )


def refresh_local_delivery_route_execution_instance(
    route_solution: RouteSolution | None,
    *,
    recompute_mode: str = INCREMENTAL_RECOMPUTE,
    recompute_from_position: int = 1,
    time_zone: str | None = None,
    warning_sink=None,
) -> tuple[RouteSolution | None, list[RouteSolutionStop]]:
    if route_solution is None:
        return None, []

    normalized_stops, normalized_start_position = normalize_route_solution_stop_ordering(
        route_solution
    )
    db.session.flush()

    effective_start_position = 1
    if recompute_mode != FULL_RECOMPUTE:
        effective_start_position = max(1, int(recompute_from_position or 1))
        if normalized_start_position is not None:
            effective_start_position = min(
                effective_start_position,
                max(1, int(normalized_start_position)),
            )

    if not any(getattr(stop, "order_id", None) for stop in (route_solution.stops or [])):
        return route_solution, dedupe_route_solution_stops(normalized_stops)

    refreshed_stops: list[RouteSolutionStop] = []
    try:
        refreshed_stops = refresh_route_solution_incremental(
            route_solution=route_solution,
            time_zone=time_zone,
            recompute_from_position=effective_start_position,
        )
    except ValidationFailed:
        raise
    except Exception as exc:
        stale_stops = mark_route_stops_stale(route_solution, effective_start_position)
        refreshed_stops = stale_stops
        _emit_refresh_warning(
            route_solution=route_solution,
            recompute_mode=recompute_mode,
            recompute_from_position=effective_start_position,
            time_zone=time_zone,
            warning_sink=warning_sink,
            error=exc,
        )

    return route_solution, dedupe_route_solution_stops(
        [*normalized_stops, *(refreshed_stops or [])]
    )


def load_route_solution_for_refresh(route_solution_id: int | None) -> RouteSolution | None:
    if route_solution_id is None:
        return None

    return (
        db.session.query(RouteSolution)
        .filter(RouteSolution.id == route_solution_id)
        .options(
            selectinload(RouteSolution.stops),
            joinedload(RouteSolution.route_group)
            .joinedload(RouteGroup.route_plan)
            .selectinload(RoutePlan.orders),
        )
        .populate_existing()
        .one_or_none()
    )


def dedupe_route_solution_stops(
    stops: Iterable[RouteSolutionStop] | None,
) -> list[RouteSolutionStop]:
    deduped: list[RouteSolutionStop] = []
    seen_keys: set[tuple[str, str]] = set()

    for stop in stops or []:
        stop_id = getattr(stop, "id", None)
        client_id = getattr(stop, "client_id", None)
        key = (
            "id" if stop_id is not None else "client_id",
            str(stop_id if stop_id is not None else client_id),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(stop)

    return sorted(
        deduped,
        key=lambda stop: (
            stop.stop_order if getattr(stop, "stop_order", None) is not None else 10**9,
            getattr(stop, "id", 10**9),
            getattr(stop, "client_id", ""),
        ),
    )


def sync_route_solution_stop_count(route_solution: RouteSolution | None) -> int:
    if route_solution is None or route_solution.id is None:
        return 0

    stop_count = (
        db.session.query(func.count(RouteSolutionStop.id))
        .filter(RouteSolutionStop.route_solution_id == route_solution.id)
        .scalar()
        or 0
    )
    return int(stop_count)


def _emit_refresh_warning(
    *,
    route_solution: RouteSolution,
    recompute_mode: str,
    recompute_from_position: int,
    time_zone: str | None,
    warning_sink,
    error: Exception,
) -> None:
    logger.warning(
        "Route refresh failed route_id=%s recompute_mode=%s recompute_from_position=%s time_zone=%s",
        route_solution.id,
        recompute_mode,
        recompute_from_position,
        time_zone,
        exc_info=error,
    )
    if warning_sink is not None and hasattr(warning_sink, "set_warning"):
        warning_sink.set_warning(
            f"Route timings could not be refreshed for route {route_solution.id}: {error}"
        )


def mark_route_stops_stale(
    route_solution: RouteSolution,
    start_position: int,
) -> list[RouteSolutionStop]:
    from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync.incremental_sync import (
        mark_route_stops_stale as _mark_route_stops_stale,
    )

    return _mark_route_stops_stale(route_solution, start_position)
