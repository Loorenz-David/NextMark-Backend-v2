from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Mapping, Optional

from Delivery_app_BK.errors import ValidationFailed


ServiceTimePayload = Dict[str, int]


def normalize_service_time_payload(
    value: Any,
    *,
    field: str = "service_time",
    strict: bool = False,
) -> ServiceTimePayload | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        if strict:
            raise ValidationFailed(f"{field} must be an object.")
        return None

    has_time = "time" in value
    has_per_item = "per_item" in value
    if strict and not has_time and not has_per_item:
        raise ValidationFailed(f"{field} must include at least one of: time, per_item.")

    time_value = _coerce_non_negative_int(value.get("time")) if has_time else None
    per_item_value = _coerce_non_negative_int(value.get("per_item")) if has_per_item else None

    if strict and has_time and time_value is None:
        raise ValidationFailed(f"{field}.time must be a non-negative integer.")
    if strict and has_per_item and per_item_value is None:
        raise ValidationFailed(f"{field}.per_item must be a non-negative integer.")

    if time_value is None and per_item_value is None:
        return None

    return {
        "time": time_value or 0,
        "per_item": per_item_value or 0,
    }


def resolve_effective_service_time_payload(
    stop_service_time: Any,
    route_solution_service_time: Any,
) -> ServiceTimePayload | None:
    stop_payload = normalize_service_time_payload(stop_service_time)
    if stop_payload is not None:
        return stop_payload
    return normalize_service_time_payload(route_solution_service_time)


def resolve_order_item_quantity(order: Any) -> int:
    total = 0
    for item in list(getattr(order, "items", None) or []):
        quantity = _coerce_non_negative_int(getattr(item, "quantity", None))
        total += quantity if quantity is not None else 1
    return max(total, 0)


def calculate_service_time_seconds(
    service_time_payload: Any,
    item_quantity: int,
) -> Optional[int]:
    payload = normalize_service_time_payload(service_time_payload)
    if payload is None:
        return None

    safe_quantity = max(0, int(item_quantity or 0))
    total_seconds = payload["time"] + (safe_quantity * payload["per_item"])
    return max(0, int(total_seconds))


def parse_duration_seconds(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    parsed = str(value).strip().lower()
    if not parsed:
        return None

    suffix_map = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
    }
    for suffix, multiplier in suffix_map.items():
        if parsed.endswith(suffix):
            numeric = parsed[: -len(suffix)].strip()
            try:
                return int(float(numeric) * multiplier)
            except ValueError:
                return None

    if ":" in parsed:
        try:
            parts = [int(part) for part in parsed.split(":")]
            while len(parts) < 3:
                parts.append(0)
            hours, minutes, seconds = parts[:3]
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            return None

    try:
        return int(float(parsed))
    except ValueError:
        return None


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if value < 0 or not value.is_integer():
            return None
        return int(value)
    if isinstance(value, str):
        parsed = value.strip()
        if not parsed:
            return None
        if not parsed.isdigit():
            return None
        return int(parsed)
    return None


def resolve_expected_service_duration_seconds(
    *,
    stop_service_time: Any,
    route_solution_service_time: Any,
    item_quantity: int,
    legacy_service_duration: Any = None,
) -> int | None:
    effective_service_time = resolve_effective_service_time_payload(
        stop_service_time,
        route_solution_service_time,
    )
    calculated = calculate_service_time_seconds(
        effective_service_time,
        item_quantity,
    )
    if calculated is not None:
        return max(0, int(calculated))

    parsed_legacy = parse_duration_seconds(legacy_service_duration)
    if parsed_legacy is None:
        return None
    return max(0, int(parsed_legacy))


def derive_expected_departure_time(
    expected_arrival_time: Any,
    expected_service_duration_seconds: int | None,
):
    if expected_arrival_time is None:
        return None
    service_seconds = max(0, int(expected_service_duration_seconds or 0))
    return expected_arrival_time + timedelta(seconds=service_seconds)


def apply_expected_stop_schedule(
    stop: Any,
    *,
    expected_arrival_time,
    expected_service_duration_seconds: int | None,
) -> None:
    if expected_arrival_time is None:
        clear_expected_stop_schedule(stop)
        return

    normalized_service_seconds = max(0, int(expected_service_duration_seconds or 0))
    stop.expected_arrival_time = expected_arrival_time
    stop.expected_service_duration_seconds = normalized_service_seconds
    stop.expected_departure_time = derive_expected_departure_time(
        expected_arrival_time,
        normalized_service_seconds,
    )


def clear_expected_stop_schedule(stop: Any) -> None:
    stop.expected_arrival_time = None
    stop.expected_service_duration_seconds = None
    stop.expected_departure_time = None
