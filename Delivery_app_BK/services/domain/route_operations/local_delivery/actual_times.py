from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import RouteSolution


def resolve_actual_timestamp(value: datetime | None) -> datetime:
    if value is not None:
        return value
    return datetime.now(timezone.utc)


def ensure_route_solution_actual_start_time(
    route_solution: RouteSolution,
    candidate_time: datetime | None,
) -> bool:
    if route_solution.actual_start_time is not None or candidate_time is None:
        return False

    route_solution.actual_start_time = candidate_time
    return True
