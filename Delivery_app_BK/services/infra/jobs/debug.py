from __future__ import annotations

from dataclasses import asdict, dataclass

from rq.registry import FailedJobRegistry

from Delivery_app_BK.services.infra.jobs.queues import get_named_queue, get_queue_names


@dataclass(frozen=True)
class FailedJobRecord:
    job_id: str
    queue: str
    description: str
    enqueued_at: str | None
    ended_at: str | None
    exc_info: str | None


def get_queue_summary() -> dict[str, int]:
    names = get_queue_names()
    return {
        names.events: get_named_queue("events").count,
        names.messaging: get_named_queue("messaging").count,
        names.realtime: get_named_queue("realtime").count,
        names.default: get_named_queue("default").count,
    }


def list_failed_jobs(*, queue_key: str | None = None, limit: int = 20) -> list[dict]:
    queue_keys = [queue_key] if queue_key else ["events", "messaging", "realtime", "default"]
    records: list[dict] = []

    for current_queue_key in queue_keys:
        queue = get_named_queue(current_queue_key)
        registry = FailedJobRegistry(queue=queue)
        job_ids = registry.get_job_ids()[:limit]

        for job_id in job_ids:
            job = queue.fetch_job(job_id)
            if job is None:
                continue
            records.append(
                asdict(
                    FailedJobRecord(
                        job_id=job.id,
                        queue=queue.name,
                        description=job.description or job.func_name,
                        enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else None,
                        ended_at=job.ended_at.isoformat() if job.ended_at else None,
                        exc_info=job.exc_info,
                    )
                )
            )

    return records
