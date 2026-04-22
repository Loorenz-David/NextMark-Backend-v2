from __future__ import annotations

import logging

import requests

from Delivery_app_BK.models import Order, OrderScheduleTarget, db
from Delivery_app_BK.services.domain.order.shopify import should_notify_order_schedule


logger = logging.getLogger(__name__)


def notify_order_schedule(
    target_id: int,
    order_id: int,
    scheduled_date: str,
) -> dict:
    target = db.session.get(OrderScheduleTarget, target_id)
    if target is None or not target.is_active:
        return {"status": "skipped", "reason": "Schedule target is missing or inactive"}

    order = db.session.get(Order, order_id)
    if order is None or not should_notify_order_schedule(order):
        return {"status": "skipped", "reason": "Order is missing or not eligible for schedule notification"}

    response = requests.post(
        target.endpoint_url,
        headers={
            "x-api-key": target.api_key,
            "Content-Type": "application/json",
        },
        json={
            "shopId": target.external_shop_id,
            "orderId": order.external_order_id,
            "scheduledDate": scheduled_date,
        },
        timeout=10,
    )
    response.raise_for_status()

    logger.info(
        "Order schedule notified | target=%s order_id=%s external_order_id=%s date=%s",
        target_id,
        order_id,
        order.external_order_id,
        scheduled_date,
    )
    return {"status": "sent"}
