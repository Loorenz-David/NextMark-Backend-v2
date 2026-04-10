from enum import Enum

from Delivery_app_BK.errors import ValidationFailed


class VehicleStatus(str, Enum):
    IDLE = "idle"
    IN_ROUTE = "in_route"
    LOADING = "loading"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


VALID_VEHICLE_STATUSES = {member.value for member in VehicleStatus}


def validate_vehicle_status(value: str) -> str:
    """Validate vehicle status and return canonical lowercase value."""
    if value is None:
        raise ValidationFailed("status is required.")

    normalized = value.strip().lower()
    if normalized not in VALID_VEHICLE_STATUSES:
        raise ValidationFailed(
            f"Invalid status '{value}'. Must be one of: {', '.join(sorted(VALID_VEHICLE_STATUSES))}"
        )
    return normalized
