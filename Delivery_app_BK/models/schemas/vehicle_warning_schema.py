"""
Schema definition for vehicle-level route warnings.

Vehicle warnings are stored in route_solution.route_warnings alongside
time-based warnings and follow the same base shape (type, severity, message)
with additional numeric context fields.
"""

VEHICLE_WARNING_TYPES = {
    "vehicle_max_volume_exceeded",
    "vehicle_max_weight_exceeded",
    "vehicle_max_distance_exceeded",
    "vehicle_max_duration_exceeded",
}

VEHICLE_WARNING_SCHEMA = {
    "type": "object",
    "required": ["type", "severity", "message"],
    "properties": {
        "type": {"type": "string", "enum": list(VEHICLE_WARNING_TYPES)},
        "severity": {"type": "string", "enum": ["warning", "error"]},
        "message": {"type": "string", "minLength": 1},
        "actual_value": {"type": "number"},
        "limit_value": {"type": "number"},
    },
    "additionalProperties": False,
}


def build_vehicle_warning(
    warning_type: str,
    actual_value: float,
    limit_value: float,
    message: str,
) -> dict:
    """Build a vehicle warning dict matching the vehicle warning schema."""
    if warning_type not in VEHICLE_WARNING_TYPES:
        raise ValueError(f"Unknown vehicle warning type: {warning_type}")
    return {
        "type": warning_type,
        "severity": "warning",
        "message": message,
        "actual_value": actual_value,
        "limit_value": limit_value,
    }
