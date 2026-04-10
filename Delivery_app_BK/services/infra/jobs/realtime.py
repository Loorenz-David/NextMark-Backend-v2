from __future__ import annotations

from Delivery_app_BK.services.infra.jobs import REALTIME_RETRY_POLICY, enqueue_job
from Delivery_app_BK.services.infra.jobs.tasks.realtime import (
    relay_app_event_job,
    relay_order_event_job,
)


def enqueue_order_realtime_relay(event_row_id: int) -> None:
    enqueue_job(
        queue_key="realtime",
        fn=relay_order_event_job,
        args=(event_row_id,),
        retry_policy=REALTIME_RETRY_POLICY,
        description=f"relay:order-event:{event_row_id}",
    )


def enqueue_app_realtime_relay(event_row_id: int) -> None:
    enqueue_job(
        queue_key="realtime",
        fn=relay_app_event_job,
        args=(event_row_id,),
        retry_policy=REALTIME_RETRY_POLICY,
        description=f"relay:app-event:{event_row_id}",
    )
