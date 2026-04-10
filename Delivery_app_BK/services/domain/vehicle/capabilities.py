from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class VehicleCapability(str, Enum):
    COLD_CHAIN = "cold_chain"
    FRAGILE = "fragile"
    HEAVY_LOAD = "heavy_load"
    RETURNS = "returns"
    OVERSIZED = "oversized"


VALID_VEHICLE_CAPABILITIES = {member.value for member in VehicleCapability}


def validate_vehicle_capabilities(value):
    """Validate capability list and return normalized lowercase values without duplicates."""
    if value is None:
        return None

    if not isinstance(value, list):
        raise ValidationFailed("capabilities must be a list of strings.")

    normalized = []
    seen = set()

    for idx, capability in enumerate(value):
        if not isinstance(capability, str):
            raise ValidationFailed(f"capabilities[{idx}] must be a string.")

        item = capability.strip().lower()
        if item not in VALID_VEHICLE_CAPABILITIES:
            raise ValidationFailed(
                f"Invalid capability '{capability}'. Must be one of: {', '.join(sorted(VALID_VEHICLE_CAPABILITIES))}"
            )

        if item in seen:
            continue

        seen.add(item)
        normalized.append(item)

    return normalized
