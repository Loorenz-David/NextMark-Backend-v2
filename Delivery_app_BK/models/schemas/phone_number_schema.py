PHONE_NUMBER_SCHEMA = {
    "type": "object",
    "required": ["prefix", "number"],
    "properties": {
        "prefix": {"type": "string", "minLength": 1},
        "number": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}
