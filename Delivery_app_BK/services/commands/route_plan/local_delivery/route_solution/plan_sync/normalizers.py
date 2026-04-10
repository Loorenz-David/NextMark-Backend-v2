from datetime import datetime, timezone
from typing import Optional


def ensure_utc(value: datetime | None) -> datetime | None:
    if not value:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_time_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    parsed = str(value).strip()
    if not parsed:
        return None
    return parsed


def normalize_skip_reason(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value
