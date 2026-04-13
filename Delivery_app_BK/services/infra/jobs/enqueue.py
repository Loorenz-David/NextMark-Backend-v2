from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from rq.job import Job
from rq_scheduler import Scheduler

from Delivery_app_BK.services.infra.jobs.queues import get_named_queue
from Delivery_app_BK.services.infra.jobs.retries import DEFAULT_RETRY_POLICY, RetryPolicy
from Delivery_app_BK.services.infra.redis import get_current_rq_redis_connection


def enqueue_job(
    *,
    queue_key: str,
    fn: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    job_id: str | None = None,
    retry_policy: RetryPolicy | None = None,
    description: str | None = None,
    result_ttl: int = 300,
    failure_ttl: int = 7 * 24 * 3600,
) -> Job:
    queue = get_named_queue(queue_key)
    policy = retry_policy or DEFAULT_RETRY_POLICY



    job = queue.enqueue_call(
        func=fn,
        args=args,
        kwargs=kwargs or {},
        job_id=job_id,
        retry=policy.to_rq_retry(),
        description=description,
        result_ttl=result_ttl,
        failure_ttl=failure_ttl,
    )



    return job


def schedule_job(
    *,
    queue_key: str,
    fn: Callable[..., Any],
    scheduled_time: datetime,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    job_id: str | None = None,
    retry_policy: RetryPolicy | None = None,
    interval: int | None = None,
    repeat: int | None = None,
) -> Job:
    queue = get_named_queue(queue_key)
    scheduler = Scheduler(queue=queue, connection=get_current_rq_redis_connection())
    safe_job_id = job_id.replace(":", "-") if job_id else job_id
    return scheduler.schedule(
        scheduled_time=scheduled_time,
        func=fn,
        args=args,
        kwargs=kwargs or {},
        interval=interval,
        repeat=repeat,
        id=safe_job_id,
        queue_name=queue.name,
    )
