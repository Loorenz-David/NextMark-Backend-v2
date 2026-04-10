from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed


def parse_datetime_utc(value) -> datetime | None:
    parsed: datetime | None = None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_start_date(value) -> datetime:
    parsed = parse_datetime_utc(value)
    if not parsed:
        raise ValidationFailed("start_date must be a valid date.")
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0)


def normalize_end_date(value) -> datetime:
    parsed = parse_datetime_utc(value)
    if not parsed:
        raise ValidationFailed("end_date must be a valid date.")
    return parsed.replace(hour=23, minute=59, second=59, microsecond=0)


def default_end_date(start_date: datetime) -> datetime:
    return start_date.replace(hour=23, minute=59, second=59, microsecond=0)


def parse_optional_datetime(value, *, field: str) -> datetime | None:
    if value is None:
        return None
    parsed = parse_datetime_utc(value)
    if not parsed:
        raise ValidationFailed(f"{field} must be a valid date.")
    return parsed


def validate_time_range(
        start_time: str | datetime,
        end_time: str | datetime,
        *,
        label
):
    start = parse_datetime_utc(start_time)
    end = parse_datetime_utc(end_time)

    if not start or not end:
        raise ValidationFailed(f"{label} start and end dates are required.")
    if end < start:
        raise ValidationFailed(f"{label} end date cannot be before start date.")
