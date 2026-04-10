SERVICE_TIME_SCHEMA = {
    "type": "object",
    "required": ["time", "per_item"],
    "properties": {
        "time": {"type": "integer", "minimum": 0},
        "per_item": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}
