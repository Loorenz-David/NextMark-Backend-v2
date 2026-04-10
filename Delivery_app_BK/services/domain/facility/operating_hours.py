import re
from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class WeekDay(str, Enum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


VALID_WEEK_DAYS = {day.value for day in WeekDay}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def validate_operating_hours(value):
    """
    Validate operating hours payload.

    Expected shape:
      [{"day": "mon", "open": "08:00", "close": "18:00"}, ...]
    """
    if value is None:
        return None

    if not isinstance(value, list):
        raise ValidationFailed("operating_hours must be a list of day windows.")

    normalized_windows = []
    seen_days = set()

    for idx, window in enumerate(value):
        if not isinstance(window, dict):
            raise ValidationFailed(
                f"operating_hours[{idx}] must be an object with day/open/close keys."
            )

        day = window.get("day")
        open_time = window.get("open")
        close_time = window.get("close")

        if not isinstance(day, str):
            raise ValidationFailed(f"operating_hours[{idx}].day must be a string.")

        day_normalized = day.strip().lower()
        if day_normalized not in VALID_WEEK_DAYS:
            allowed = ", ".join(sorted(VALID_WEEK_DAYS))
            raise ValidationFailed(
                f"operating_hours[{idx}].day '{day}' is invalid. Must be one of: {allowed}"
            )

        if day_normalized in seen_days:
            raise ValidationFailed(
                f"operating_hours contains duplicate day '{day_normalized}'."
            )
        seen_days.add(day_normalized)

        if not isinstance(open_time, str) or not TIME_RE.match(open_time):
            raise ValidationFailed(
                f"operating_hours[{idx}].open must be in HH:MM 24h format."
            )

        if not isinstance(close_time, str) or not TIME_RE.match(close_time):
            raise ValidationFailed(
                f"operating_hours[{idx}].close must be in HH:MM 24h format."
            )

        if _to_minutes(close_time) <= _to_minutes(open_time):
            raise ValidationFailed(
                f"operating_hours[{idx}] must have close later than open."
            )

        normalized_windows.append(
            {
                "day": day_normalized,
                "open": open_time,
                "close": close_time,
            }
        )

    return normalized_windows
