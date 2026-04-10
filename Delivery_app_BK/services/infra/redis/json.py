from __future__ import annotations

import json
from datetime import datetime


def dumps_json(value) -> str:
    return json.dumps(value, default=_json_default, separators=(",", ":"))


def loads_json(value: str | bytes | None):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")
