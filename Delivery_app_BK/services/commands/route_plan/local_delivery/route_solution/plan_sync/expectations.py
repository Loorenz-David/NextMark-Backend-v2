from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.models.mixins.validation_mixins.time_warning_validation import (
    TimeWarningFactory,
)


def apply_expected_start_from_window(
    route_solution: RouteSolution,
    window: tuple[datetime, datetime] | None,
) -> None:
    if not window:
        return
    route_solution.expected_start_time = window[0]


def apply_expected_end_shift_from_window(
    route_solution: RouteSolution,
    old_window: tuple[datetime, datetime],
    new_window: tuple[datetime, datetime],
    shift_times: bool,
) -> None:
    if not shift_times:
        return
    if route_solution.expected_end_time is None:
        return

    old_start = old_window[0]
    new_start = new_window[0]
    if old_start is None or new_start is None:
        return

    shift_delta: timedelta = new_start - old_start
    if shift_delta.total_seconds() == 0:
        return

    route_solution.expected_end_time = route_solution.expected_end_time + shift_delta


def sync_route_end_warning(
    route_solution: RouteSolution,
    allowed_end: datetime | None,
) -> None:
    warnings = list(route_solution.route_warnings or [])
    filtered = [
        warning
        for warning in warnings
        if warning.get("type") != "route_end_time_exceeded"
    ]

    expected_end = _ensure_utc(route_solution.expected_end_time)
    allowed_end = _ensure_utc(allowed_end)
    if expected_end and allowed_end and expected_end > allowed_end:
        filtered.append(
            TimeWarningFactory.route_end_time_exceeded(
                expected_end=expected_end,
                allowed_end=allowed_end,
            )
        )

    route_solution.route_warnings = filtered or None
    route_solution.has_route_warnings = bool(filtered)


def _ensure_utc(value: datetime | None) -> datetime | None:
    if not value:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
