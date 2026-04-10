
TIME_WARNING_SCHEMA = {
    "type": "object",
    "required": ["type", "severity", "message"],
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "time_window_violation",
                "optimization_window_excluded",
                "route_end_time_exceeded",
                "low_slack"
            ]
        },
        "severity": {
            "type": "string",
            "enum": ["info", "warning", "error"]
        },
        "message": {
            "type": "string",
            "minLength": 1
        },

        # Optional contextual fields
        "expected_time": {"type": "string"},
        "allowed_start": {"type": "string"},
        "allowed_end": {"type": "string"},
        "slack_minutes": {"type": "number"},
        "route_expected_end": {"type": "string"},
        "route_allowed_end": {"type": "string"}
    },
    "additionalProperties": False
}
