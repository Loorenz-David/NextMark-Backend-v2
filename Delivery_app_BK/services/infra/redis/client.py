from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from flask import current_app
from redis import Redis, ConnectionPool


_pool: ConnectionPool | None = None


def _normalize_redis_uri(redis_uri: str) -> str:
    parsed = urlparse(redis_uri)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("REDIS_URI must use redis:// or rediss://.")
    return redis_uri


def describe_redis_uri(redis_uri: str) -> str:
    parsed = urlparse(_normalize_redis_uri(redis_uri))
    db = parsed.path.lstrip("/") or "0"
    host = parsed.hostname or "unknown-host"
    port = parsed.port or (6380 if parsed.scheme == "rediss" else 6379)
    return f"{parsed.scheme}://{host}:{port}/{db}"


def get_redis_uri() -> str:
    redis_uri = current_app.config.get("REDIS_URI")
    if not redis_uri:
        raise RuntimeError("REDIS_URI is not configured.")
    return _normalize_redis_uri(redis_uri)


@lru_cache(maxsize=8)
def get_redis_connection(redis_uri: str, *, decode_responses: bool = True) -> Redis:
    return Redis.from_url(redis_uri, decode_responses=decode_responses)


def get_current_redis_connection() -> Redis:
    return get_redis_connection(get_redis_uri())


def get_rq_redis_connection(redis_uri: str) -> Redis:
    pool = get_redis_pool(redis_uri)
    return Redis(connection_pool=pool)



def get_current_rq_redis_connection() -> Redis:
    return get_rq_redis_connection(get_redis_uri())


def assert_redis_available(redis_uri: str, *, decode_responses: bool = True) -> Redis:
    connection = get_redis_connection(redis_uri, decode_responses=decode_responses)
    connection.ping()
    return connection


def assert_current_redis_available(*, decode_responses: bool = True) -> Redis:
    return assert_redis_available(get_redis_uri(), decode_responses=decode_responses)




def get_redis_pool(redis_uri: str) -> ConnectionPool:
    global _pool

    if _pool is None:
        _pool = ConnectionPool.from_url(
            redis_uri,
            max_connections=50,
            decode_responses=False,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )

    return _pool