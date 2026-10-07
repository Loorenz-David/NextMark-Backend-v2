import logging

from Delivery_app_BK.models import Order, OrderScheduleTarget, RoutePlan, db
from Delivery_app_BK.services.domain.order.shopify import (
    is_shopify_order,
    should_fulfill_shopify_order,
    should_notify_order_schedule,
)
from Delivery_app_BK.services.infra.events.handlers.order._actions import run_immediate_action
from Delivery_app_BK.services.infra.jobs import enqueue_job

# Task modules import command packages that import this events package back,
# so the two jobs enqueued directly here are imported at call time.


logger = logging.getLogger(__name__)


def sync_shopify_fulfillment_on_order_completed(order_event) -> None:
    from Delivery_app_BK.services.infra.tasks.order.fulfill_shopify_order import fulfill_shopify_order

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


def sync_shopify_costumer_on_client_form_submitted(order_event) -> None:
    from Delivery_app_BK.services.infra.tasks.order.sync_shopify import sync_shopify

    event_order_id = getattr(order_event, "order_id", None)
    logger.info(
        "[shopify-costumer-sync] handler fired event_name=%s order_id=%s",
        getattr(order_event, "event_name", None),
        event_order_id,
    )
    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, event_order_id)
    if order is None:
        logger.warning(
            "[shopify-costumer-sync] handler: order not found order_id=%s",
            event_order_id,
        )
        return
    if not is_shopify_order(order):
        logger.info(
            "[shopify-costumer-sync] handler: not a shopify order, skip "
            "order_id=%s external_source=%s external_order_id=%s",
            order.id,
            getattr(order, "external_source", None),
            getattr(order, "external_order_id", None),
        )
        return

    logger.info(
        "[shopify-costumer-sync] handler: enqueue sync_shopify order_id=%s",
        order.id,
    )
    enqueue_job(
        queue_key="default",
        fn=sync_shopify,
        args=(order.id,),
        description=f"sync-shopify-costumer:{order.id}",
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


def push_external_schedule_on_delivery_rescheduled(order_event) -> None:
    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not is_shopify_order(order):
        return

    run_immediate_action(
        order_event,
        "order_external_schedule_push",
    )


def push_external_schedule_on_delivery_plan_unassigned(order_event) -> None:
    payload = getattr(order_event, "payload", None) or {}
    new_plan_id = payload.get("new_route_plan_id")
    if new_plan_id is None:
        new_plan_id = payload.get("new_delivery_plan_id")
    if new_plan_id is not None:
        return

    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not is_shopify_order(order):
        return

    run_immediate_action(
        order_event,
        "order_external_schedule_push",
        action_scope="unassigned",
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
            action_scope=f"target:{target.id}",
            payload={
                "target_id": target.id,
                "scheduled_date": scheduled_date,
            },
        )
