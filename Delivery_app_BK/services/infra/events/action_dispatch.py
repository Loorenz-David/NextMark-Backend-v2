from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import RoutePlanEventAction, OrderEventAction, db
from Delivery_app_BK.services.infra.jobs import MESSAGING_RETRY_POLICY, enqueue_job, schedule_job
from Delivery_app_BK.services.infra.tasks.route_plan.send_email import send_email as send_route_plan_email
from Delivery_app_BK.services.infra.tasks.route_plan.send_sms import send_sms as send_route_plan_sms
from Delivery_app_BK.services.infra.tasks.order.send_email import send_email as send_order_email
from Delivery_app_BK.services.infra.tasks.order.send_sms import send_sms as send_order_sms


def enqueue_order_action(action: OrderEventAction) -> None:
    if action.status != OrderEventAction.STATUS_PENDING:
        return
    task = _resolve_order_action_task(action.action_name)
    _dispatch_action(
        action=action,
        task=task,
        job_id=f"order-action:{action.id}",
        description=f"order-action:{action.action_name}:{action.id}",
    )


def enqueue_route_plan_action(action: RoutePlanEventAction) -> None:
    if action.status != RoutePlanEventAction.STATUS_PENDING:
        return
    task = _resolve_route_plan_action_task(action.action_name)
    _dispatch_action(
        action=action,
        task=task,
        job_id=f"plan-action:{action.id}",
        description=f"route-plan-action:{action.action_name}:{action.id}",
    )


def _resolve_order_action_task(action_name: str):
    if action_name.endswith("_sms"):
        return send_order_sms
    if action_name.endswith("_email"):
        return send_order_email
    raise ValueError(f"Unsupported order event action '{action_name}'.")


def _resolve_route_plan_action_task(action_name: str):
    if action_name.endswith("_sms"):
        return send_route_plan_sms
    if action_name.endswith("_email"):
        return send_route_plan_email
    raise ValueError(f"Unsupported route plan event action '{action_name}'.")


def _dispatch_action(*, action, task, job_id: str, description: str) -> None:
    now = datetime.now(timezone.utc)
    if action.scheduled_for is not None and action.scheduled_for > now:
        schedule_job(
            queue_key="messaging",
            fn=task,
            scheduled_time=action.scheduled_for,
            args=(action.id,),
            job_id=job_id,
            retry_policy=MESSAGING_RETRY_POLICY,
        )
    else:
        enqueue_job(
            queue_key="messaging",
            fn=task,
            args=(action.id,),
            retry_policy=MESSAGING_RETRY_POLICY,
            description=description,
        )

    action.enqueued_at = now
    action.last_error = None
    db.session.commit()
