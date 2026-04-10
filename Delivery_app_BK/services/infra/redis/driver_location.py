from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from .client import get_current_redis_connection
from .json import dumps_json, loads_json
from .keys import build_driver_location_key, build_driver_location_scan_pattern


def set_latest_driver_location(team_id: int, driver_id: int, payload: dict) -> None:
    redis = get_current_redis_connection()
    key = build_driver_location_key(team_id, driver_id)
    ttl_seconds = int(current_app.config.get("REDIS_DRIVER_LOCATION_TTL_SECONDS", 45))
    normalized = {
        "driver_id": int(driver_id),
        "team_id": int(team_id),
        "coords": payload.get("coords") or {},
        "heading": payload.get("heading"),
        "speed": payload.get("speed"),
        "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
    }
    redis.set(key, dumps_json(normalized), ex=ttl_seconds)


def list_latest_driver_locations(team_id: int) -> list[dict]:
    redis = get_current_redis_connection()
    pattern = build_driver_location_scan_pattern(team_id)
    payloads: list[dict] = []
    for key in redis.scan_iter(match=pattern):
        payload = loads_json(redis.get(key))
        if isinstance(payload, dict):
            payloads.append(payload)
    payloads.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return payloads
