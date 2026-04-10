from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Team, db
from Delivery_app_BK.services.context import ServiceContext

MAX_ORDER_DELIVERY_WINDOWS = 14
DEFAULT_ORDER_TIME_ZONE = "UTC"
ORDER_DELIVERY_WINDOW_TYPES = {
    "EXACT_DATETIME",
    "DATE_ONLY",
    "TIME_RANGE",
    "DATE_RANGE",
    "FULL_RANGE",
}


class DeliveryWindowValidationFailed(ValidationFailed):
    code = "VALIDATION_ERROR"


class DeliveryWindowPastTimeError(DeliveryWindowValidationFailed):
    code = "DELIVERY_WINDOW_PAST_TIME"


class DeliveryWindowOverlapError(DeliveryWindowValidationFailed):
    code = "DELIVERY_WINDOW_OVERLAP"


class DeliveryWindowLimitExceededError(DeliveryWindowValidationFailed):
    code = "DELIVERY_WINDOW_LIMIT_EXCEEDED"


@dataclass(frozen=True)
class ParsedOrderDeliveryWindow:
    client_id: str | None
    start_at: datetime
    end_at: datetime
    window_type: str


def resolve_order_delivery_windows_timezone(ctx: ServiceContext) -> ZoneInfo:
    # Resolution order is deterministic and fixed for the full request:
    # team.time_zone -> identity.time_zone -> UTC.
    team_id = getattr(ctx, "team_id", None)
    if isinstance(team_id, int):
        team = db.session.get(Team, team_id)
        team_tz = _normalize_timezone_name(getattr(team, "time_zone", None))
        if team_tz:
            return team_tz

    identity = getattr(ctx, "identity", None) or {}
    identity_tz = _normalize_timezone_name(identity.get("time_zone"))
    if identity_tz:
        return identity_tz

    return ZoneInfo(DEFAULT_ORDER_TIME_ZONE)


def validate_and_normalize_delivery_windows(
    value: Any,
    *,
    field: str = "delivery_windows",
) -> list[ParsedOrderDeliveryWindow]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of objects.")
    if len(value) > MAX_ORDER_DELIVERY_WINDOWS:
        raise DeliveryWindowLimitExceededError(f"{field} supports at most {MAX_ORDER_DELIVERY_WINDOWS} windows.")

    parsed_rows: list[ParsedOrderDeliveryWindow] = []
    for index, row in enumerate(value):
        row_field = f"{field}[{index}]"
        if not isinstance(row, dict):
            raise ValidationFailed(f"{row_field} must be an object.")

        start_at = _parse_strict_utc_datetime(row.get("start_at"), field=f"{row_field}.start_at")
        end_at = _parse_strict_utc_datetime(row.get("end_at"), field=f"{row_field}.end_at")
        if start_at < datetime.now(timezone.utc):
            raise DeliveryWindowPastTimeError(f"{row_field}.start_at cannot be in the past.")
        if end_at <= start_at:
            raise ValidationFailed(f"{row_field}.end_at must be greater than {row_field}.start_at.")

        window_type = row.get("window_type")
        if not isinstance(window_type, str) or not window_type.strip():
            raise ValidationFailed(f"{row_field}.window_type is required.")
        window_type = window_type.strip()
        if window_type not in ORDER_DELIVERY_WINDOW_TYPES:
            raise ValidationFailed(
                f"{row_field}.window_type '{window_type}' is invalid. Allowed values: {sorted(ORDER_DELIVERY_WINDOW_TYPES)}",
            )

        client_id = row.get("client_id")
        if client_id is not None and not isinstance(client_id, str):
            raise ValidationFailed(f"{row_field}.client_id must be a string when provided.")

        parsed_rows.append(
            ParsedOrderDeliveryWindow(
                client_id=client_id.strip() if isinstance(client_id, str) and client_id.strip() else None,
                start_at=start_at,
                end_at=end_at,
                window_type=window_type,
            )
        )

    sorted_rows = sort_delivery_windows(parsed_rows)
    validate_non_overlapping_delivery_windows(sorted_rows, field=field)
    return sorted_rows


def sort_delivery_windows(
    windows: list[ParsedOrderDeliveryWindow],
) -> list[ParsedOrderDeliveryWindow]:
    return sorted(windows, key=lambda row: (row.start_at, row.end_at))


def validate_non_overlapping_delivery_windows(
    windows: list[ParsedOrderDeliveryWindow],
    *,
    field: str = "delivery_windows",
) -> None:
    for index in range(1, len(windows)):
        previous = windows[index - 1]
        current = windows[index]
        # Half-open intervals: [start_at, end_at). Adjacency is valid.
        if current.start_at < previous.end_at:
            raise DeliveryWindowOverlapError(
                f"{field}[{index}] overlaps with a previous delivery window.",
            )


def validate_same_local_day_delivery_windows(
    windows: list[ParsedOrderDeliveryWindow],
    *,
    team_timezone: ZoneInfo,
    field: str = "delivery_windows",
) -> None:
    for index, row in enumerate(windows):
        local_start = row.start_at.astimezone(team_timezone)
        local_end = row.end_at.astimezone(team_timezone)
        if local_start.date() != local_end.date():
            raise ValidationFailed(
                f"{field}[{index}] crosses local day boundaries in timezone '{team_timezone.key}'.",
            )


def sort_delivery_window_instances(instances: list[Any] | None) -> list[Any]:
    source = instances or []
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        source,
        key=lambda row: (
            getattr(row, "start_at", None) or minimum,
            getattr(row, "end_at", None) or minimum,
        ),
    )


def _parse_strict_utc_datetime(value: Any, *, field: str) -> datetime:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValidationFailed(f"{field} is required.")
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValidationFailed(f"{field} must be a valid ISO datetime.") from exc
    else:
        raise ValidationFailed(f"{field} must be a datetime string.")

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ValidationFailed(f"{field} must be timezone-aware UTC.")

    if parsed.utcoffset() != timedelta(0):
        raise ValidationFailed(f"{field} must be UTC with +00:00 offset.")

    return parsed.astimezone(timezone.utc)


def _normalize_timezone_name(value: Any) -> ZoneInfo | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None
