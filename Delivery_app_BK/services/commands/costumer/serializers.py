from __future__ import annotations

import re
from typing import Any

from Delivery_app_BK.errors import ValidationFailed


HH_MM_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_required_name_fields(fields: dict[str, Any]) -> None:
    if not fields.get("first_name"):
        raise ValidationFailed("first_name is required")
    if not fields.get("last_name"):
        raise ValidationFailed("last_name is required")


def validate_and_normalize_phone(phone: Any) -> dict[str, str] | None:
    if phone is None:
        return None
    if not isinstance(phone, dict):
        raise ValidationFailed("phone must be an object with 'prefix' and 'number'")

    prefix = str(phone.get("prefix") or "").strip().replace(" ", "")
    number = str(phone.get("number") or "").strip().replace(" ", "")

    if not prefix or not number:
        raise ValidationFailed("phone.prefix and phone.number are required")
    if not prefix.startswith("+"):
        raise ValidationFailed("phone.prefix must start with '+'")
    if not prefix[1:].isdigit():
        raise ValidationFailed("phone.prefix must contain digits after '+'")
    if not number.isdigit():
        raise ValidationFailed("phone.number must contain only digits")

    return {
        "prefix": prefix,
        "number": number,
    }


def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


def normalize_operating_hours_entry(entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValidationFailed("operating_hours entries must be objects")

    if "weekday" not in entry:
        raise ValidationFailed("operating_hours.weekday is required")

    weekday = entry.get("weekday")
    if not isinstance(weekday, int) or weekday < 0 or weekday > 6:
        raise ValidationFailed("weekday must be an integer between 0 and 6")

    is_closed = bool(entry.get("is_closed", False))
    open_time = entry.get("open_time")
    close_time = entry.get("close_time")

    if is_closed:
        # Current schema keeps open/close non-null; use deterministic placeholders.
        return {
            "client_id": entry.get("client_id"),
            "weekday": weekday,
            "is_closed": True,
            "open_time": "00:00",
            "close_time": "00:00",
        }

    if not isinstance(open_time, str) or not isinstance(close_time, str):
        raise ValidationFailed("open_time and close_time are required when is_closed is false")
    if not HH_MM_PATTERN.match(open_time) or not HH_MM_PATTERN.match(close_time):
        raise ValidationFailed("open_time and close_time must be formatted as HH:MM")

    open_minutes = _hh_mm_to_minutes(open_time)
    close_minutes = _hh_mm_to_minutes(close_time)
    if open_minutes >= close_minutes:
        raise ValidationFailed("open_time must be earlier than close_time")

    return {
        "client_id": entry.get("client_id"),
        "weekday": weekday,
        "is_closed": False,
        "open_time": open_time,
        "close_time": close_time,
    }


def validate_unique_weekdays(entries: list[dict[str, Any]]) -> None:
    weekdays: set[int] = set()
    for entry in entries:
        weekday = entry["weekday"]
        if weekday in weekdays:
            raise ValidationFailed(f"Duplicate weekday in operating_hours payload: {weekday}")
        weekdays.add(weekday)


def validate_int_id_list(values: Any, field_name: str) -> list[int]:
    if values is None:
        return []
    if not isinstance(values, list) or not all(isinstance(v, int) for v in values):
        raise ValidationFailed(f"{field_name} must be a list of integers")
    return values


def normalized_phone_string(phone: Any) -> str | None:
    normalized = validate_and_normalize_phone(phone)
    if not normalized:
        return None
    return f"{normalized['prefix']}{normalized['number']}"


def _hh_mm_to_minutes(value: str) -> int:
    hours = int(value[:2])
    minutes = int(value[3:5])
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValidationFailed("HH:MM must be a valid 24-hour time")
    return (hours * 60) + minutes
