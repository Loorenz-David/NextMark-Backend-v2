from __future__ import annotations

import re
from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.constants.route_end_strategy import (
    CUSTOM_END_ADDRESS,
    LAST_STOP,
    ROUND_TRIP,
)
from Delivery_app_BK.services.domain.vehicle.capabilities import (
    VALID_VEHICLE_CAPABILITIES,
)

HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ALLOWED_ROUTE_END_STRATEGIES = {ROUND_TRIP, CUSTOM_END_ADDRESS, LAST_STOP}
_ALLOWED_FIELDS = {
    "name",
    "default_facility_id",
    "max_orders_per_route",
    "max_vehicles",
    "operating_window_start",
    "operating_window_end",
    "eta_tolerance_seconds",
    "vehicle_capabilities_required",
    "preferred_vehicle_ids",
    "default_route_end_strategy",
    "meta",
}


@dataclass
class ZoneTemplateRequest:
    name: str
    default_facility_id: int | None
    max_orders_per_route: int | None
    max_vehicles: int | None
    operating_window_start: str | None
    operating_window_end: str | None
    eta_tolerance_seconds: int
    vehicle_capabilities_required: list[str] | None
    preferred_vehicle_ids: list[int] | None
    default_route_end_strategy: str
    meta: dict | None


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _validate_hhmm(value, *, field: str) -> str | None:
    """Accept HH:MM strings only. Returns None if value is None."""
    if value is None:
        return None
    if not isinstance(value, str) or not HHMM_RE.match(value):
        raise ValidationFailed(f"{field} must be in HH:MM format.")
    return value


def _validate_window(start: str | None, end: str | None) -> None:
    """If both are set, end must be strictly after start."""
    if start is None or end is None:
        return
    if _to_minutes(end) <= _to_minutes(start):
        raise ValidationFailed("operating_window_end must be later than operating_window_start.")


def _validate_capabilities(value, *, field: str) -> list[str] | None:
    """Validate each item is a known VehicleCapability string. Deduplicate."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of strings.")

    normalized: list[str] = []
    seen = set()
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise ValidationFailed(f"{field}[{idx}] must be a string.")
        capability = item.strip().lower()
        if capability not in VALID_VEHICLE_CAPABILITIES:
            allowed = ", ".join(sorted(VALID_VEHICLE_CAPABILITIES))
            raise ValidationFailed(
                f"{field}[{idx}] '{item}' is invalid. Must be one of: {allowed}"
            )
        if capability in seen:
            continue
        seen.add(capability)
        normalized.append(capability)
    return normalized


def _validate_route_end_strategy(value, *, field: str) -> str:
    """Validate against route end strategy constants. Accepts 'last_stop' as alias for 'end_at_last_stop'."""
    if value is None:
        return ROUND_TRIP
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string.")

    normalized = value.strip().lower()
    
    # Alias mapping: "last_stop" → canonical LAST_STOP constant ("end_at_last_stop")
    alias_map = {
        "last_stop": LAST_STOP,
    }
    
    # Use mapped value if it's an alias, otherwise check against allowed strategies
    if normalized in alias_map:
        return alias_map[normalized]
    
    if normalized not in ALLOWED_ROUTE_END_STRATEGIES:
        allowed = ", ".join(sorted(ALLOWED_ROUTE_END_STRATEGIES))
        raise ValidationFailed(f"{field} must be one of: {allowed}")
    return normalized


def _validate_positive_int(value, *, field: str) -> int | None:
    """Accept int >= 1. Returns None if value is None."""
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationFailed(f"{field} must be an integer >= 1.")
    return value


def _validate_list_of_positive_ints(value, *, field: str) -> list[int] | None:
    """Accept list where each item is a positive integer."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of positive integers.")

    validated: list[int] = []
    for idx, item in enumerate(value):
        if not isinstance(item, int) or isinstance(item, bool) or item < 1:
            raise ValidationFailed(f"{field}[{idx}] must be a positive integer.")
        validated.append(item)
    return validated


def parse_zone_template_request(raw: dict) -> ZoneTemplateRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Request body must be an object.")

    unknown_fields = sorted(set(raw.keys()) - _ALLOWED_FIELDS)
    if unknown_fields:
        raise ValidationFailed(
            f"Unknown fields for zone template: {', '.join(unknown_fields)}"
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationFailed("name is required.")

    default_facility_id = _validate_positive_int(
        raw.get("default_facility_id"),
        field="default_facility_id",
    )
    max_orders_per_route = _validate_positive_int(
        raw.get("max_orders_per_route"),
        field="max_orders_per_route",
    )
    max_vehicles = _validate_positive_int(raw.get("max_vehicles"), field="max_vehicles")

    operating_window_start = _validate_hhmm(
        raw.get("operating_window_start"),
        field="operating_window_start",
    )
    operating_window_end = _validate_hhmm(
        raw.get("operating_window_end"),
        field="operating_window_end",
    )
    _validate_window(operating_window_start, operating_window_end)

    eta_tolerance_seconds = raw.get("eta_tolerance_seconds", 0)
    if (
        not isinstance(eta_tolerance_seconds, int)
        or isinstance(eta_tolerance_seconds, bool)
        or eta_tolerance_seconds < 0
        or eta_tolerance_seconds > 7200
    ):
        raise ValidationFailed("eta_tolerance_seconds must be an integer between 0 and 7200.")

    vehicle_capabilities_required = _validate_capabilities(
        raw.get("vehicle_capabilities_required"),
        field="vehicle_capabilities_required",
    )
    preferred_vehicle_ids = _validate_list_of_positive_ints(
        raw.get("preferred_vehicle_ids"),
        field="preferred_vehicle_ids",
    )
    default_route_end_strategy = _validate_route_end_strategy(
        raw.get("default_route_end_strategy"),
        field="default_route_end_strategy",
    )

    meta = raw.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise ValidationFailed("meta must be an object.")

    return ZoneTemplateRequest(
        name=name.strip(),
        default_facility_id=default_facility_id,
        max_orders_per_route=max_orders_per_route,
        max_vehicles=max_vehicles,
        operating_window_start=operating_window_start,
        operating_window_end=operating_window_end,
        eta_tolerance_seconds=eta_tolerance_seconds,
        vehicle_capabilities_required=vehicle_capabilities_required,
        preferred_vehicle_ids=preferred_vehicle_ids,
        default_route_end_strategy=default_route_end_strategy,
        meta=meta,
    )
