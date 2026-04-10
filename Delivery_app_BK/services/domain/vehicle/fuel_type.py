from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class FuelType(str, Enum):
    BENSINE = "bensine"
    DIESEL = "diesel"
    ELECTRIC = "electric"


VALID_FUEL_TYPES = {member.value for member in FuelType}


def validate_fuel_type(value: str) -> str:
    """Validate fuel type and return canonical lowercase value."""
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized not in VALID_FUEL_TYPES:
        raise ValidationFailed(
            f"Invalid fuel_type '{value}'. Must be one of: {', '.join(sorted(VALID_FUEL_TYPES))}"
        )
    return normalized
