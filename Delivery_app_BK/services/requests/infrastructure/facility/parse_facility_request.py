from dataclasses import dataclass, field
from typing import Any, Optional

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.facility import (
    validate_facility_type,
    validate_operating_hours,
)


_CREATE_ALLOWED_FIELDS = {
    "client_id",
    "name",
    "property_location",
    "facility_type",
    "can_dispatch",
    "can_receive_returns",
    "operating_hours",
    "default_loading_time_seconds",
    "default_unloading_time_seconds",
    "max_orders_per_day",
    "external_refs",
}

_UPDATE_ALLOWED_FIELDS = _CREATE_ALLOWED_FIELDS - {"client_id"}


@dataclass
class FacilityCreateRequest:
    name: str
    facility_type: str
    client_id: Optional[str] = None
    property_location: dict | None = None
    can_dispatch: bool = False
    can_receive_returns: bool = False
    operating_hours: list[dict] | None = None
    default_loading_time_seconds: int = 600
    default_unloading_time_seconds: int = 300
    max_orders_per_day: int | None = None
    external_refs: dict | None = None

    def to_fields_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "property_location": self.property_location,
            "facility_type": self.facility_type,
            "can_dispatch": self.can_dispatch,
            "can_receive_returns": self.can_receive_returns,
            "operating_hours": self.operating_hours,
            "default_loading_time_seconds": self.default_loading_time_seconds,
            "default_unloading_time_seconds": self.default_unloading_time_seconds,
            "max_orders_per_day": self.max_orders_per_day,
            "external_refs": self.external_refs,
        }


@dataclass
class FacilityUpdateRequest:
    name: Optional[str] = None
    property_location: dict | None = None
    facility_type: Optional[str] = None
    can_dispatch: Optional[bool] = None
    can_receive_returns: Optional[bool] = None
    operating_hours: list[dict] | None = None
    default_loading_time_seconds: Optional[int] = None
    default_unloading_time_seconds: Optional[int] = None
    max_orders_per_day: int | None = None
    external_refs: dict | None = None
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


def _validate_required_name(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationFailed("name is required.")
    return value.strip()


def _validate_bool(value, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationFailed(f"{field_name} must be a boolean.")
    return value


def _validate_non_negative_int(value, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationFailed(f"{field_name} must be an integer >= 0.")
    return value


def _validate_optional_positive_int(value, *, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationFailed(f"{field_name} must be an integer >= 1.")
    return value


def _validate_optional_object(value, *, field_name: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field_name} must be an object.")
    return value


def parse_create_facility_request(raw: dict) -> FacilityCreateRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Facility create payload must be an object.")

    _validate_unknown_fields(raw, allowed_fields=_CREATE_ALLOWED_FIELDS, entity_name="facility")

    return FacilityCreateRequest(
        client_id=_validate_optional_string(raw.get("client_id"), field_name="client_id"),
        name=_validate_required_name(raw.get("name")),
        property_location=_validate_optional_object(
            raw.get("property_location"),
            field_name="property_location",
        ),
        facility_type=validate_facility_type(raw.get("facility_type")),
        can_dispatch=_validate_bool(raw["can_dispatch"], field_name="can_dispatch")
        if "can_dispatch" in raw
        else False,
        can_receive_returns=_validate_bool(
            raw["can_receive_returns"],
            field_name="can_receive_returns",
        )
        if "can_receive_returns" in raw
        else False,
        operating_hours=validate_operating_hours(raw.get("operating_hours")),
        default_loading_time_seconds=_validate_non_negative_int(
            raw.get("default_loading_time_seconds", 600),
            field_name="default_loading_time_seconds",
        ),
        default_unloading_time_seconds=_validate_non_negative_int(
            raw.get("default_unloading_time_seconds", 300),
            field_name="default_unloading_time_seconds",
        ),
        max_orders_per_day=_validate_optional_positive_int(
            raw.get("max_orders_per_day"),
            field_name="max_orders_per_day",
        ),
        external_refs=_validate_optional_object(
            raw.get("external_refs"),
            field_name="external_refs",
        ),
    )


def parse_update_facility_request(raw: dict) -> FacilityUpdateRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Facility update payload must be an object.")

    _validate_unknown_fields(raw, allowed_fields=_UPDATE_ALLOWED_FIELDS, entity_name="facility")

    fields = {}

    if "name" in raw:
        name = _validate_optional_string(raw["name"], field_name="name")
        if name is None:
            raise ValidationFailed("name cannot be empty.")
        fields["name"] = name

    if "property_location" in raw:
        fields["property_location"] = _validate_optional_object(
            raw["property_location"],
            field_name="property_location",
        )

    if "facility_type" in raw:
        fields["facility_type"] = validate_facility_type(raw["facility_type"])

    if "can_dispatch" in raw:
        fields["can_dispatch"] = _validate_bool(raw["can_dispatch"], field_name="can_dispatch")

    if "can_receive_returns" in raw:
        fields["can_receive_returns"] = _validate_bool(
            raw["can_receive_returns"],
            field_name="can_receive_returns",
        )

    if "operating_hours" in raw:
        fields["operating_hours"] = validate_operating_hours(raw["operating_hours"])

    if "default_loading_time_seconds" in raw:
        fields["default_loading_time_seconds"] = _validate_non_negative_int(
            raw["default_loading_time_seconds"],
            field_name="default_loading_time_seconds",
        )

    if "default_unloading_time_seconds" in raw:
        fields["default_unloading_time_seconds"] = _validate_non_negative_int(
            raw["default_unloading_time_seconds"],
            field_name="default_unloading_time_seconds",
        )

    if "max_orders_per_day" in raw:
        fields["max_orders_per_day"] = _validate_optional_positive_int(
            raw["max_orders_per_day"],
            field_name="max_orders_per_day",
        )

    if "external_refs" in raw:
        fields["external_refs"] = _validate_optional_object(
            raw["external_refs"],
            field_name="external_refs",
        )

    return FacilityUpdateRequest(
        **fields,
        provided_fields=set(fields.keys()),
    )