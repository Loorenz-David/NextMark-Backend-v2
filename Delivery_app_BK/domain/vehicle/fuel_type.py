from Delivery_app_BK.errors import ValidationFailed

VALID_FUEL_TYPES = {"bensine", "diesel", "electric"}


def validate_fuel_type(value: str) -> str:
    """Validate fuel type. Returns the stored canonical value."""
    if value is None:
        return None
    lower = value.lower()
    if lower not in VALID_FUEL_TYPES:
        raise ValidationFailed(
            f"Invalid fuel_type '{value}'. Must be one of: {', '.join(sorted(VALID_FUEL_TYPES))}"
        )
    return lower
