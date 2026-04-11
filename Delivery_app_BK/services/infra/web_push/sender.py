"""
Web Push sender.

Sends standards-compliant Web Push messages to browser subscriptions using
VAPID authentication. Automatically deactivates subscriptions that are
reported as gone or expired by the push service (HTTP 404 / 410).

Usage:
    from Delivery_app_BK.services.infra.web_push.sender import send_web_push_to_users

    send_web_push_to_users(
        user_ids=[42],
        title="New message",
        description="Order case #123 has a new message",
        notification_id="uuid-...",
        occurred_at="2026-04-11T12:00:00Z",
        target={"kind": "order_case_chat", "params": {"orderCaseId": 123}},
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from flask import current_app
from pywebpush import WebPushException, webpush

from Delivery_app_BK.models import PushSubscription, db

logger = logging.getLogger(__name__)


def _build_payload(
    notification_id: str,
    occurred_at: str,
    title: str,
    description: str,
    target: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "notification": {
                "notification_id": notification_id,
                "occurred_at": occurred_at,
                "title": title,
                "description": description,
                "target": target,
            }
        }
    )


def _deactivate_subscription(subscription: PushSubscription) -> None:
    subscription.is_active = False
    subscription.updated_at = datetime.now(timezone.utc)
    db.session.commit()


def _send_to_subscription(
    subscription: PushSubscription,
    payload: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
) -> None:
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=payload,
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (404, 410):
            logger.info(
                "Push subscription gone (status=%s), deactivating endpoint=%s",
                status_code,
                subscription.endpoint,
            )
            _deactivate_subscription(subscription)
        else:
            logger.warning(
                "Failed to deliver web push to endpoint=%s (status=%s): %s",
                subscription.endpoint,
                status_code,
                exc,
            )


def send_web_push_to_users(
    user_ids: list[int],
    title: str,
    description: str,
    notification_id: str,
    occurred_at: str,
    target: dict[str, Any],
) -> None:
    vapid_private_key: str | None = current_app.config.get("WEB_PUSH_VAPID_PRIVATE_KEY")
    vapid_subject: str = current_app.config.get(
        "WEB_PUSH_VAPID_SUBJECT", "mailto:admin@nextmark.app"
    )

    if not vapid_private_key:
        logger.error("WEB_PUSH_VAPID_PRIVATE_KEY is not configured — cannot send web push.")
        return

    subscriptions: list[PushSubscription] = (
        PushSubscription.query.filter(
            PushSubscription.user_id.in_(user_ids),
            PushSubscription.is_active.is_(True),
        ).all()
    )

    if not subscriptions:
        return

    payload = _build_payload(
        notification_id=notification_id,
        occurred_at=occurred_at,
        title=title,
        description=description,
        target=target,
    )
    vapid_claims = {"sub": vapid_subject}

    for subscription in subscriptions:
        _send_to_subscription(subscription, payload, vapid_private_key, vapid_claims)
