from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from flask import current_app

from .client import get_current_redis_connection
from .json import dumps_json, loads_json
from .keys import (
    build_notification_count_key,
    build_notification_payload_key,
    build_notification_unread_key,
)


def _ttl_seconds() -> int:
    return int(current_app.config.get("REDIS_NOTIFICATION_TTL_SECONDS", 60 * 60 * 48))


def add_unread_notification(*, user_id: int, app_scope: str, notification: dict) -> None:
    redis = get_current_redis_connection()
    notification_id = str(notification.get("notification_id") or "").strip()
    if not notification_id:
        return

    payload_key = build_notification_payload_key(notification_id)
    unread_key = build_notification_unread_key(user_id, app_scope)
    count_key = build_notification_count_key(user_id, app_scope)
    ttl_seconds = _ttl_seconds()
    occurred_at = notification.get("occurred_at")
    score = _to_timestamp(occurred_at)
    _prune_expired_unread_entries(
        redis=redis,
        user_id=user_id,
        app_scope=app_scope,
        ttl_seconds=ttl_seconds,
    )
    already_exists = redis.zscore(unread_key, notification_id) is not None
    unread_count = int(redis.zcard(unread_key) or 0) + (0 if already_exists else 1)

    with redis.pipeline() as pipe:
        pipe.set(payload_key, dumps_json(notification), ex=ttl_seconds)
        pipe.zadd(unread_key, {notification_id: score})
        pipe.expire(unread_key, ttl_seconds)
        pipe.set(count_key, unread_count)
        pipe.expire(count_key, ttl_seconds)
        pipe.execute()


def list_unread_notifications(*, user_id: int, app_scope: str, limit: int = 50) -> list[dict]:
    redis = get_current_redis_connection()
    unread_key = build_notification_unread_key(user_id, app_scope)
    ttl_seconds = _ttl_seconds()
    _prune_expired_unread_entries(
        redis=redis,
        user_id=user_id,
        app_scope=app_scope,
        ttl_seconds=ttl_seconds,
    )
    notification_ids = redis.zrevrange(unread_key, 0, max(0, limit - 1))
    payloads: list[dict] = []
    stale_ids: list[str] = []

    for notification_id in notification_ids:
        payload = loads_json(redis.get(build_notification_payload_key(notification_id)))
        if isinstance(payload, dict):
            payloads.append(payload)
        else:
            stale_ids.append(notification_id)

    if stale_ids:
        remaining = max(0, int(redis.zcard(unread_key) or 0) - len(stale_ids))
        with redis.pipeline() as pipe:
            for notification_id in stale_ids:
                pipe.zrem(unread_key, notification_id)
            pipe.set(build_notification_count_key(user_id, app_scope), remaining)
            pipe.expire(build_notification_count_key(user_id, app_scope), ttl_seconds)
            pipe.execute()

    payloads.sort(key=lambda item: str(item.get("occurred_at", "")), reverse=True)
    return payloads


def mark_notifications_read(*, user_id: int, app_scope: str, notification_ids: Iterable[str]) -> int:
    redis = get_current_redis_connection()
    unread_key = build_notification_unread_key(user_id, app_scope)
    count_key = build_notification_count_key(user_id, app_scope)
    normalized_ids = [str(notification_id).strip() for notification_id in notification_ids if str(notification_id).strip()]
    if not normalized_ids:
        return 0

    ttl_seconds = _ttl_seconds()
    _prune_expired_unread_entries(
        redis=redis,
        user_id=user_id,
        app_scope=app_scope,
        ttl_seconds=ttl_seconds,
    )
    removed = int(redis.zrem(unread_key, *normalized_ids) or 0)
    remaining = int(redis.zcard(unread_key) or 0)
    with redis.pipeline() as pipe:
        pipe.set(count_key, remaining)
        pipe.expire(count_key, ttl_seconds)
        pipe.expire(unread_key, ttl_seconds)
        pipe.execute()
    return removed


def get_unread_count(*, user_id: int, app_scope: str) -> int:
    redis = get_current_redis_connection()
    ttl_seconds = _ttl_seconds()
    remaining = _prune_expired_unread_entries(
        redis=redis,
        user_id=user_id,
        app_scope=app_scope,
        ttl_seconds=ttl_seconds,
    )
    raw = redis.get(build_notification_count_key(user_id, app_scope))
    if raw is None:
        return remaining
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return remaining


def _prune_expired_unread_entries(
    *,
    redis,
    user_id: int,
    app_scope: str,
    ttl_seconds: int,
) -> int:
    unread_key = build_notification_unread_key(user_id, app_scope)
    count_key = build_notification_count_key(user_id, app_scope)
    cutoff_score = datetime.now(timezone.utc).timestamp() - ttl_seconds
    removed = int(redis.zremrangebyscore(unread_key, "-inf", cutoff_score) or 0)
    remaining = int(redis.zcard(unread_key) or 0)

    if removed > 0 or redis.get(count_key) is None:
        with redis.pipeline() as pipe:
            pipe.set(count_key, remaining)
            pipe.expire(count_key, ttl_seconds)
            if remaining > 0:
                pipe.expire(unread_key, ttl_seconds)
            pipe.execute()

    return remaining


def _to_timestamp(value: object) -> float:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return datetime.now(timezone.utc).timestamp()

    return datetime.now(timezone.utc).timestamp()
