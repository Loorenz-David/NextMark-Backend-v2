from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from redis import Redis
from rq import Queue

from Delivery_app_BK.services.infra.redis import get_current_rq_redis_connection


HASH_TAG = "{rq}"

EVENTS_QUEUE = f"{HASH_TAG}:events"
DEFAULT_QUEUE = f"{HASH_TAG}:default"
REALTIME_QUEUE = f"{HASH_TAG}:realtime"
MESSAGING_QUEUE = f"{HASH_TAG}:messaging"




@dataclass(frozen=True)
class QueueNames:
    events: str = EVENTS_QUEUE
    messaging: str = MESSAGING_QUEUE
    realtime: str = REALTIME_QUEUE
    default: str = DEFAULT_QUEUE


def get_queue_names() -> QueueNames:
    return QueueNames(
        events=current_app.config.get("RQ_EVENTS_QUEUE", EVENTS_QUEUE),
        messaging=current_app.config.get("RQ_MESSAGING_QUEUE", MESSAGING_QUEUE),
        realtime=current_app.config.get("RQ_REALTIME_QUEUE", REALTIME_QUEUE),
        default=current_app.config.get("RQ_DEFAULT_QUEUE", DEFAULT_QUEUE),
    )


def get_queue(name: str, connection: Redis | None = None) -> Queue:
    
    return Queue(
        name, 
        connection=connection or get_current_rq_redis_connection(), 
        default_timeout=600,
        prefix=f"rq:{name}"
        
        )


def get_named_queue(queue_key: str, connection: Redis | None = None) -> Queue:
    queue_names = get_queue_names()
    return get_queue(getattr(queue_names, queue_key), connection=connection)
