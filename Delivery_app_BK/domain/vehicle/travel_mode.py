from Delivery_app_BK.errors import ValidationFailed

VALID_TRAVEL_MODES = {"DRIVING", "TWO_WHEELER", "BICYCLING", "WALKING"}

GOOGLE_TRAVEL_MODE_MAP = {
    "DRIVING": "DRIVING",
    "TWO_WHEELER": "TWO_WHEELER",
    "BICYCLING": "BICYCLING",
    "WALKING": "WALKING",
}


def validate_travel_mode(value: str) -> str:
    """Validate and normalize travel mode. Returns the stored canonical value."""
    if value is None:
        return None
    upper = value.upper()
    if upper not in VALID_TRAVEL_MODES:
        raise ValidationFailed(
            f"Invalid travel_mode '{value}'. Must be one of: {', '.join(sorted(VALID_TRAVEL_MODES))}"
        )
    return upper


def map_to_google_travel_mode(stored_value: str) -> str:
    """Map a stored travel mode value to its Google-compatible equivalent."""
    if stored_value is None:
        return "DRIVING"
    mapped = GOOGLE_TRAVEL_MODE_MAP.get(stored_value.upper())
    if mapped is None:
        raise ValidationFailed(
            f"Cannot map travel_mode '{stored_value}' to a Google travel mode."
        )
    return mapped
