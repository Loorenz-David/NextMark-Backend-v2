from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class TravelMode(str, Enum):
    DRIVING = "DRIVING"
    TWO_WHEELER = "TWO_WHEELER"
    BICYCLING = "BICYCLING"
    WALKING = "WALKING"


VALID_TRAVEL_MODES = {member.value for member in TravelMode}

GOOGLE_TRAVEL_MODE_MAP = {
    TravelMode.DRIVING.value: "DRIVING",
    TravelMode.TWO_WHEELER.value: "TWO_WHEELER",
    TravelMode.BICYCLING.value: "BICYCLING",
    TravelMode.WALKING.value: "WALKING",
}


def validate_travel_mode(value: str) -> str:
    """Validate travel mode and return canonical uppercase value."""
    if value is None:
        return None

    normalized = value.strip().upper()
    if normalized not in VALID_TRAVEL_MODES:
        raise ValidationFailed(
            f"Invalid travel_mode '{value}'. Must be one of: {', '.join(sorted(VALID_TRAVEL_MODES))}"
        )
    return normalized


def map_to_google_travel_mode(stored_value: str) -> str:
    if stored_value is None:
        return TravelMode.DRIVING.value

    normalized = validate_travel_mode(stored_value)
    mapped = GOOGLE_TRAVEL_MODE_MAP.get(normalized)
    if mapped is None:
        raise ValidationFailed(
            f"Cannot map travel_mode '{stored_value}' to a Google travel mode."
        )
    return mapped
