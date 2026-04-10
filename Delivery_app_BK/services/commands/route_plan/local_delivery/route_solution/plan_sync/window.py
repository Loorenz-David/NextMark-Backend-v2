from datetime import datetime
from typing import Optional, Tuple

from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    combine_plan_date_and_local_hhmm_to_utc,
    ensure_utc_datetime,
    resolve_request_timezone,
)
from Delivery_app_BK.errors import ValidationFailed


def resolve_window(
    plan_start: datetime,
    plan_end: datetime,
    set_start_time: Optional[str],
    set_end_time: Optional[str],
    *,
    time_zone: str | None = None,
) -> Optional[Tuple[datetime, datetime]]:
    start_date = ensure_utc_datetime(plan_start)
    end_date = ensure_utc_datetime(plan_end)
    if not start_date or not end_date:
        return None

    request_timezone = resolve_request_timezone(
        identity={"time_zone": time_zone} if time_zone else None,
    )
    window_start = combine_plan_date_and_local_hhmm_to_utc(
        start_date,
        set_start_time or "00:00:00",
        request_timezone,
    )
    end_plan_date = start_date if set_end_time else end_date
    window_end = combine_plan_date_and_local_hhmm_to_utc(
        end_plan_date,
        set_end_time or "23:59:59",
        request_timezone,
    )

    return window_start, window_end


def validate_window(window: Optional[Tuple[datetime, datetime]]) -> None:
    if not window:
        return
    if window[1] < window[0]:
        raise ValidationFailed("Route solution end time cannot be before start time.")
