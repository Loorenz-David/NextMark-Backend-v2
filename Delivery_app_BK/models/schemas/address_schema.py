ADDRESS_SCHEMA = {
    "type": "object",
    "required": ["street_address", "coordinates","country"],
    "properties": {
        "street_address": {"type": "string", "minLength": 0},
        "postal_code": {"type": "string", "minLength": 0},
        "country": {"type": "string", "minLength": 0},
        "city": {"type": "string", "minLength": 0},
        "coordinates": {
            "type": "object",
            "required": ["lat", "lng"],
            "properties": {
                "lat": {"type": "number"},
                "lng": {"type": "number"}
            }
        }
    },
    "additionalProperties": False
}