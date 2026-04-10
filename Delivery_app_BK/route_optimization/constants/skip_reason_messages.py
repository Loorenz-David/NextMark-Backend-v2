from __future__ import annotations

from typing import Any, Iterable

SKIPPED_REASON_MESSAGES = {
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_TIME_WINDOWS": (
        "Cannot be performed within the vehicle time windows."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_DISTANCE_LIMIT": (
        "Cannot be performed within the vehicle distance limit."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_TRAVEL_DURATION_LIMIT": (
        "Cannot be performed within the vehicle travel duration limit."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_CAPACITY": (
        "Cannot be performed within the vehicle capacity limits."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_TRAVEL_DURATION_SOFT_LIMIT": (
        "Cannot be performed within the vehicle travel duration soft limit."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_DISTANCE_SOFT_LIMIT": (
        "Cannot be performed within the vehicle distance soft limit."
    ),
    "CANNOT_BE_PERFORMED_WITHIN_VEHICLE_TIME_WINDOWS_SOFT_LIMIT": (
        "Cannot be performed within the vehicle time windows soft limit."
    ),
}


def resolve_skip_reason_message(reason: Any) -> str | None:
    if not reason:
        return None
    codes = _extract_codes(reason)
    if not codes:
        return None
    messages = [
        SKIPPED_REASON_MESSAGES.get(code, code) for code in codes if isinstance(code, str)
    ]
    if not messages:
        return None
    return "; ".join(messages)


def _extract_codes(reason: Any) -> list[str]:
    if isinstance(reason, str):
        return [reason]
    if isinstance(reason, dict):
        code = reason.get("code")
        return [code] if isinstance(code, str) else []
    if isinstance(reason, Iterable):
        codes = []
        for entry in reason:
            if isinstance(entry, str):
                codes.append(entry)
            elif isinstance(entry, dict):
                code = entry.get("code")
                if isinstance(code, str):
                    codes.append(code)
        return codes
    return []
