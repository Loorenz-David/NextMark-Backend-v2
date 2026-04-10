from dataclasses import dataclass, field
from typing import Any, Optional

from Delivery_app_BK.services.domain.vehicle import (
    validate_vehicle_capabilities,
    validate_travel_mode,
    validate_fuel_type,
    validate_vehicle_status,
)
from Delivery_app_BK.errors import ValidationFailed


_CREATE_ALLOWED_FIELDS = {
    "client_id",
    "registration_number",
    "label",
    "fuel_type",
    "travel_mode",
    "max_volume_load_cm3",
    "max_weight_load_g",
    "max_speed_kmh",
    "cost_per_km",
    "cost_per_hour",
    "travel_distance_limit_km",
    "travel_duration_limit_minutes",
    "home_facility_id",
    "status",
    "is_active",
    "capabilities",
    "loading_time_per_stop_seconds",
    "unloading_time_per_stop_seconds",
    "fixed_cost",
}

_UPDATE_ALLOWED_FIELDS = _CREATE_ALLOWED_FIELDS - {"client_id"}


@dataclass
class VehicleCreateRequest:
    registration_number: str
    client_id: Optional[str] = None
    label: Optional[str] = None
    fuel_type: Optional[str] = None
    travel_mode: Optional[str] = None
    max_volume_load_cm3: Optional[int] = None
    max_weight_load_g: Optional[int] = None
    max_speed_kmh: Optional[float] = None
    cost_per_km: float = 0
    cost_per_hour: float = 0
    travel_distance_limit_km: Optional[int] = None
    travel_duration_limit_minutes: Optional[int] = None
    home_facility_id: Optional[int] = None
    status: str = "idle"
    is_active: bool = True
    capabilities: Optional[list[str]] = None
    loading_time_per_stop_seconds: int = 0
    unloading_time_per_stop_seconds: int = 0
    fixed_cost: float = 0.0

    def to_fields_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "registration_number": self.registration_number,
            "label": self.label,
            "fuel_type": self.fuel_type,
            "travel_mode": self.travel_mode,
            "max_volume_load_cm3": self.max_volume_load_cm3,
            "max_weight_load_g": self.max_weight_load_g,
            "max_speed_kmh": self.max_speed_kmh,
            "cost_per_km": self.cost_per_km,
            "cost_per_hour": self.cost_per_hour,
            "travel_distance_limit_km": self.travel_distance_limit_km,
            "travel_duration_limit_minutes": self.travel_duration_limit_minutes,
            "home_facility_id": self.home_facility_id,
            "status": self.status,
            "is_active": self.is_active,
            "capabilities": self.capabilities,
            "loading_time_per_stop_seconds": self.loading_time_per_stop_seconds,
            "unloading_time_per_stop_seconds": self.unloading_time_per_stop_seconds,
            "fixed_cost": self.fixed_cost,
        }


@dataclass
class VehicleUpdateRequest:
    registration_number: Optional[str] = None
    label: Optional[str] = None
    fuel_type: Optional[str] = None
    travel_mode: Optional[str] = None
    max_volume_load_cm3: Optional[int] = None
    max_weight_load_g: Optional[int] = None
    max_speed_kmh: Optional[float] = None
    cost_per_km: Optional[float] = None
    cost_per_hour: Optional[float] = None
    travel_distance_limit_km: Optional[int] = None
    travel_duration_limit_minutes: Optional[int] = None
    home_facility_id: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    capabilities: Optional[list[str]] = None
    loading_time_per_stop_seconds: Optional[int] = None
    unloading_time_per_stop_seconds: Optional[int] = None
    fixed_cost: Optional[float] = None
    provided_fields: set[str] = field(default_factory=set, repr=False)

    def to_fields_dict(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in self.provided_fields
        }


def _validate_unknown_fields(raw: dict, *, allowed_fields: set[str], entity_name: str) -> None:
    unknown_fields = sorted(set(raw.keys()) - allowed_fields)
    if unknown_fields:
        raise ValidationFailed(
            f"Unknown fields for {entity_name}: {', '.join(unknown_fields)}"
        )


def _validate_optional_string(value, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailed(f"{field_name} must be a string.")

    normalized = value.strip()
    return normalized or None


def _validate_positive_int(value, *, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationFailed(f"{field_name} must be an integer >= 1.")
    return value


def _validate_non_negative_int(value, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationFailed(f"{field_name} must be an integer >= 0.")
    return value


def _validate_optional_non_negative_int(value, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _validate_non_negative_int(value, field_name=field_name)


def _validate_optional_positive_number(value, *, field_name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValidationFailed(f"{field_name} must be a number > 0.")
    return float(value)


def _validate_non_negative_number(value, *, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValidationFailed(f"{field_name} must be a number >= 0.")
    return float(value)


def _validate_bool(value, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationFailed(f"{field_name} must be a boolean.")
    return value


def parse_create_vehicle_request(raw: dict) -> VehicleCreateRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Vehicle create payload must be an object.")

    _validate_unknown_fields(raw, allowed_fields=_CREATE_ALLOWED_FIELDS, entity_name="vehicle")

    registration_number = (raw.get("registration_number") or "").strip()
    if not registration_number:
        raise ValidationFailed("registration_number is required.")

    travel_mode = validate_travel_mode(raw.get("travel_mode"))
    fuel_type = validate_fuel_type(raw.get("fuel_type"))
    status = validate_vehicle_status(raw.get("status", "idle"))

    return VehicleCreateRequest(
        client_id=_validate_optional_string(raw.get("client_id"), field_name="client_id"),
        registration_number=registration_number,
        label=_validate_optional_string(raw.get("label"), field_name="label"),
        fuel_type=fuel_type,
        travel_mode=travel_mode,
        max_volume_load_cm3=_validate_positive_int(
            raw.get("max_volume_load_cm3"),
            field_name="max_volume_load_cm3",
        ),
        max_weight_load_g=_validate_positive_int(
            raw.get("max_weight_load_g"),
            field_name="max_weight_load_g",
        ),
        max_speed_kmh=_validate_optional_positive_number(
            raw.get("max_speed_kmh"),
            field_name="max_speed_kmh",
        ),
        cost_per_km=_validate_non_negative_number(
            raw.get("cost_per_km", 0) or 0,
            field_name="cost_per_km",
        ),
        cost_per_hour=_validate_non_negative_number(
            raw.get("cost_per_hour", 0) or 0,
            field_name="cost_per_hour",
        ),
        travel_distance_limit_km=_validate_positive_int(
            raw.get("travel_distance_limit_km"),
            field_name="travel_distance_limit_km",
        ),
        travel_duration_limit_minutes=_validate_positive_int(
            raw.get("travel_duration_limit_minutes"),
            field_name="travel_duration_limit_minutes",
        ),
        home_facility_id=_validate_positive_int(
            raw.get("home_facility_id"),
            field_name="home_facility_id",
        ),
        status=status,
        is_active=_validate_bool(raw["is_active"], field_name="is_active")
        if "is_active" in raw
        else True,
        capabilities=validate_vehicle_capabilities(raw.get("capabilities")),
        loading_time_per_stop_seconds=_validate_non_negative_int(
            raw.get("loading_time_per_stop_seconds", 0),
            field_name="loading_time_per_stop_seconds",
        ),
        unloading_time_per_stop_seconds=_validate_non_negative_int(
            raw.get("unloading_time_per_stop_seconds", 0),
            field_name="unloading_time_per_stop_seconds",
        ),
        fixed_cost=_validate_non_negative_number(
            raw.get("fixed_cost", 0.0),
            field_name="fixed_cost",
        ),
    )


def parse_update_vehicle_request(raw: dict) -> VehicleUpdateRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Vehicle update payload must be an object.")

    _validate_unknown_fields(raw, allowed_fields=_UPDATE_ALLOWED_FIELDS, entity_name="vehicle")

    fields = {}

    if "registration_number" in raw:
        val = (raw["registration_number"] or "").strip()
        if not val:
            raise ValidationFailed("registration_number cannot be empty.")
        fields["registration_number"] = val

    if "travel_mode" in raw:
        fields["travel_mode"] = validate_travel_mode(raw["travel_mode"])

    if "fuel_type" in raw:
        fields["fuel_type"] = validate_fuel_type(raw["fuel_type"])

    if "status" in raw:
        fields["status"] = validate_vehicle_status(raw["status"])

    if "capabilities" in raw:
        fields["capabilities"] = validate_vehicle_capabilities(raw["capabilities"])

    if "label" in raw:
        fields["label"] = _validate_optional_string(raw["label"], field_name="label")

    if "home_facility_id" in raw:
        fields["home_facility_id"] = _validate_positive_int(
            raw["home_facility_id"],
            field_name="home_facility_id",
        )

    if "is_active" in raw:
        fields["is_active"] = _validate_bool(raw["is_active"], field_name="is_active")

    for key in (
        "max_volume_load_cm3",
        "max_weight_load_g",
        "travel_distance_limit_km",
        "travel_duration_limit_minutes",
    ):
        if key in raw:
            fields[key] = _validate_positive_int(raw[key], field_name=key)

    if "max_speed_kmh" in raw:
        fields["max_speed_kmh"] = _validate_optional_positive_number(
            raw["max_speed_kmh"],
            field_name="max_speed_kmh",
        )

    if "cost_per_km" in raw:
        fields["cost_per_km"] = _validate_non_negative_number(
            raw["cost_per_km"],
            field_name="cost_per_km",
        )

    if "cost_per_hour" in raw:
        fields["cost_per_hour"] = _validate_non_negative_number(
            raw["cost_per_hour"],
            field_name="cost_per_hour",
        )

    if "loading_time_per_stop_seconds" in raw:
        fields["loading_time_per_stop_seconds"] = _validate_optional_non_negative_int(
            raw["loading_time_per_stop_seconds"],
            field_name="loading_time_per_stop_seconds",
        )

    if "unloading_time_per_stop_seconds" in raw:
        fields["unloading_time_per_stop_seconds"] = _validate_optional_non_negative_int(
            raw["unloading_time_per_stop_seconds"],
            field_name="unloading_time_per_stop_seconds",
        )

    if "fixed_cost" in raw:
        fields["fixed_cost"] = _validate_non_negative_number(
            raw["fixed_cost"],
            field_name="fixed_cost",
        )

    return VehicleUpdateRequest(
        **fields,
        provided_fields=set(fields.keys()),
    )
