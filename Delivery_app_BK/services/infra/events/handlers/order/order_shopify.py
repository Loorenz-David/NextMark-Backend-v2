from Delivery_app_BK.models import Order, OrderScheduleTarget, RoutePlan, db
from Delivery_app_BK.services.domain.order.shopify import (
    should_fulfill_shopify_order,
    should_notify_order_schedule,
)
from Delivery_app_BK.services.infra.events.handlers.order._actions import run_immediate_action
from Delivery_app_BK.services.infra.jobs import enqueue_job
from Delivery_app_BK.services.infra.tasks.order.fulfill_shopify_order import (
    fulfill_shopify_order,
)
from Delivery_app_BK.services.infra.tasks.order.notify_order_schedule_action import (
    notify_order_schedule_action,
)


def sync_shopify_fulfillment_on_order_completed(order_event) -> None:
    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None:
        return
    if not should_fulfill_shopify_order(order):
        return

    enqueue_job(
        queue_key="default",
        fn=fulfill_shopify_order,
        args=(order.id,),
        description=f"fulfill-shopify-order:{order.id}",
    )


def notify_schedule_targets_on_order_created(order_event) -> None:
    payload = getattr(order_event, "payload", None) or {}
    delivery_plan_id = payload.get("delivery_plan_id")
    if not delivery_plan_id:
        return

    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not should_notify_order_schedule(order):
        return

    plan = db.session.get(RoutePlan, delivery_plan_id)
    start_date = getattr(plan, "start_date", None) if plan else None
    if start_date is None:
        return

    _fan_out_schedule_notification(
        order_event=order_event,
        order=order,
        scheduled_date=start_date.date().isoformat(),
    )


def notify_schedule_targets_on_delivery_rescheduled(order_event) -> None:
    payload = getattr(order_event, "payload", None) or {}
    new_plan_start = payload.get("new_plan_start")
    if not new_plan_start:
        return

    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not should_notify_order_schedule(order):
        return

    _fan_out_schedule_notification(
        order_event=order_event,
        order=order,
        scheduled_date=str(new_plan_start)[:10],
    )


def _fan_out_schedule_notification(order_event, order: Order, scheduled_date: str) -> None:
    targets = (
        db.session.query(OrderScheduleTarget)
        .filter(
            OrderScheduleTarget.team_id == order.team_id,
            OrderScheduleTarget.is_active.is_(True),
        )
        .all()
    )
    for target in targets:
        run_immediate_action(
            order_event,
            "order_schedule_notify",
            notify_order_schedule_action,
            action_scope=f"target:{target.id}",
            payload={
                "target_id": target.id,
                "scheduled_date": scheduled_date,
            },
        )
