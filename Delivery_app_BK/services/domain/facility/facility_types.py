from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class FacilityType(str, Enum):
    WAREHOUSE = "warehouse"
    DEPOT = "depot"
    HUB = "hub"
    PICKUP_POINT = "pickup_point"


VALID_FACILITY_TYPES = {member.value for member in FacilityType}


def validate_facility_type(value: str) -> str:
    """Validate and normalize facility type to canonical lowercase value."""
    if value is None:
        raise ValidationFailed("facility_type is required.")

    normalized = value.strip().lower()
    if normalized not in VALID_FACILITY_TYPES:
        allowed = ", ".join(sorted(VALID_FACILITY_TYPES))
        raise ValidationFailed(
            f"Invalid facility_type '{value}'. Must be one of: {allowed}"
        )
    return normalized
