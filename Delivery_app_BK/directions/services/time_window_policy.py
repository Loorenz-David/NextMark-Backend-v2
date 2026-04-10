from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional, Tuple

from Delivery_app_BK.models import Order, RouteSolution
from Delivery_app_BK.models.mixins.validation_mixins.time_warning_validation import (
    TimeWarningFactory,
)
from Delivery_app_BK.route_optimization.constants.skip_reasons import OUTSIDE_TIME_WINDOW

TIME_WINDOW_WARNING_TYPE = "time_window_violation"


def ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_stop_time_warnings(
    order: Optional[Order],
    arrival_time: Optional[datetime],
    route_solution: RouteSolution,
) -> List[dict]:
    if not order:
        return []
    windows = build_effective_windows(order, route_solution)
    return build_stop_time_warnings_for_windows(arrival_time, windows)


def build_stop_time_warnings_for_windows(
    arrival_time: Optional[datetime],
    windows: List[Tuple[datetime, datetime]],
) -> List[dict]:
    arrival_time = ensure_utc(arrival_time)
    normalized_windows = _normalize_windows(windows)
    if not arrival_time or not normalized_windows:
        return []

    if _is_arrival_inside_any_window(arrival_time, normalized_windows):
        return []

    reference_window = _pick_reference_window(arrival_time, normalized_windows)
    if not reference_window:
        return []

    window_start, window_end = reference_window
    return [
        TimeWarningFactory.time_window_violation(
            expected_time=arrival_time,
            window_start=window_start,
            window_end=window_end,
        ),
    ]


def apply_stop_time_window_evaluation(
    *,
    stop,
    order: Optional[Order],
    route_solution: RouteSolution,
    arrival_time: Optional[datetime] = None,
) -> bool:
    previous_state = _snapshot_warning_state(stop)
    resolved_arrival = ensure_utc(arrival_time or getattr(stop, "expected_arrival_time", None))

    warnings = build_stop_time_warnings(order, resolved_arrival, route_solution)
    _merge_time_window_warning(stop, warnings)

    current_state = _snapshot_warning_state(stop)
    return current_state != previous_state


def apply_stop_time_window_evaluation_for_windows(
    *,
    stop,
    arrival_time: Optional[datetime],
    windows: List[Tuple[datetime, datetime]],
) -> bool:
    previous_state = _snapshot_warning_state(stop)
    warnings = build_stop_time_warnings_for_windows(arrival_time, windows)
    _merge_time_window_warning(stop, warnings)
    current_state = _snapshot_warning_state(stop)
    return current_state != previous_state


def build_effective_windows(
    order: Order,
    route_solution: RouteSolution,
) -> List[Tuple[datetime, datetime]]:
    delivery_windows = _build_windows_from_delivery_windows(order)
    if delivery_windows:
        return delivery_windows

    base_date, base_end_date = _resolve_plan_window_bounds(route_solution)
    fallback_start = ensure_utc(base_date)
    fallback_end = ensure_utc(base_end_date)
    if not fallback_start or not fallback_end or fallback_end <= fallback_start:
        return []

    return [(fallback_start, fallback_end)]


def _build_windows_from_delivery_windows(order: Order) -> List[Tuple[datetime, datetime]]:
    rows = list(getattr(order, "delivery_windows", None) or [])
    windows: List[Tuple[datetime, datetime]] = []
    for row in rows:
        start = ensure_utc(_coerce_datetime(getattr(row, "start_at", None)))
        end = ensure_utc(_coerce_datetime(getattr(row, "end_at", None)))
        if not start or not end or end <= start:
            continue
        windows.append((start, end))

    return _normalize_windows(windows)


def _normalize_windows(
    windows: List[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    normalized: List[Tuple[datetime, datetime]] = []
    for window_start, window_end in windows or []:
        start = ensure_utc(window_start)
        end = ensure_utc(window_end)
        if not start or not end or end <= start:
            continue
        normalized.append((start, end))
    normalized.sort(key=lambda pair: (pair[0], pair[1]))
    return normalized


def _resolve_plan_window_bounds(
    route_solution: RouteSolution,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    plan = None
    if getattr(route_solution, "local_delivery_plan", None) is not None:
        plan = getattr(route_solution.local_delivery_plan, "delivery_plan", None)
    if not plan:
        return None, None
    return _coerce_datetime(getattr(plan, "start_date", None)), _coerce_datetime(getattr(plan, "end_date", None))


def _is_arrival_inside_any_window(
    arrival_time: datetime,
    windows: List[Tuple[datetime, datetime]],
) -> bool:
    for window_start, window_end in windows:
        if window_start <= arrival_time < window_end:
            return True
    return False


def _pick_reference_window(
    arrival_time: datetime,
    windows: List[Tuple[datetime, datetime]],
) -> Optional[Tuple[datetime, datetime]]:
    if not windows:
        return None
    if arrival_time < windows[0][0]:
        return windows[0]

    for index in range(1, len(windows)):
        previous = windows[index - 1]
        current = windows[index]
        if previous[1] <= arrival_time < current[0]:
            distance_to_previous = arrival_time - previous[1]
            distance_to_current = current[0] - arrival_time
            if distance_to_previous <= distance_to_current:
                return previous
            return current

    return windows[-1]


def _merge_time_window_warning(stop, warnings: List[dict]) -> None:
    existing = list(getattr(stop, "constraint_warnings", None) or [])
    filtered = [
        warning
        for warning in existing
        if not (isinstance(warning, dict) and warning.get("type") == TIME_WINDOW_WARNING_TYPE)
    ]

    if warnings:
        setattr(stop, "constraint_warnings", filtered + warnings)
        setattr(stop, "has_constraint_violation", True)
        setattr(stop, "reason_was_skipped", _normalize_skip_reason(OUTSIDE_TIME_WINDOW))
        return

    setattr(stop, "constraint_warnings", filtered or None)
    setattr(stop, "has_constraint_violation", bool(filtered))
    if getattr(stop, "reason_was_skipped", None) == _normalize_skip_reason(OUTSIDE_TIME_WINDOW):
        setattr(stop, "reason_was_skipped", None)


def _snapshot_warning_state(stop) -> tuple:
    return (
        bool(getattr(stop, "has_constraint_violation", False)),
        copy.deepcopy(getattr(stop, "constraint_warnings", None)),
        getattr(stop, "reason_was_skipped", None),
    )


def _normalize_skip_reason(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def resolve_next_window_start(
    arrival_time: Optional[datetime],
    windows: List[Tuple[datetime, datetime]],
) -> Optional[datetime]:
    """Return the start of the earliest window that begins after arrival_time.

    Returns None when arrival_time already falls inside a window, when there
    are no windows, or when arrival_time is past all windows.
    """
    if not arrival_time or not windows:
        return None
    arrival_time = ensure_utc(arrival_time)
    normalized = _normalize_windows(windows)
    if _is_arrival_inside_any_window(arrival_time, normalized):
        return None
    for window_start, _ in normalized:
        if window_start > arrival_time:
            return window_start
    return None


def _coerce_datetime(value: Any, tz=timezone.utc) -> Optional[datetime]:
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

    return parsed.astimezone(tz)
