from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from flask import current_app


logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_valid_strict_date(value: str) -> bool:
    if not _DATE_RE.fullmatch(value):
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except ValueError:
        return False


def push_order_schedule_update(
    *,
    shop_id: str,
    order_id: str,
    scheduled_date: str,
) -> dict:
    endpoint_url = (current_app.config.get("EXTERNAL_API_URL") or "").strip()
    external_api_key = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
    timeout_seconds = int(current_app.config.get("EXTERNAL_API_TIMEOUT_SECONDS", 10))

    if not endpoint_url:
        return {"status": "skipped", "reason": "EXTERNAL_API_URL is not configured"}
    if not external_api_key:
        return {"status": "skipped", "reason": "EXTERNAL_API_KEY is not configured"}

    normalized_shop_id = (shop_id or "").strip()
    normalized_order_id = (order_id or "").strip()
    normalized_scheduled_date = (scheduled_date or "").strip()

    if not normalized_shop_id:
        return {"status": "skipped", "reason": "shopId is required"}
    if not normalized_order_id:
        return {"status": "skipped", "reason": "orderId is required"}

    # External API accepts an empty scheduledDate when order is currently not
    # assigned to any delivery plan.
    if normalized_scheduled_date and not _is_valid_strict_date(normalized_scheduled_date):
        return {
            "status": "skipped",
            "reason": "scheduledDate must follow strict yyyy-mm-dd format or be empty",
        }

    response = requests.post(
        endpoint_url,
        headers={
            "x-api-key": external_api_key,
            "Content-Type": "application/json",
        },
        json={
            "shopId": normalized_shop_id,
            "orderId": normalized_order_id,
            "scheduledDate": normalized_scheduled_date,
        },
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        response_body = (response.text or "").strip()
        if len(response_body) > 500:
            response_body = response_body[:500]
        raise RuntimeError(
            f"External schedule push failed with status {response.status_code}. "
            f"Body: {response_body}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("External schedule push returned non-JSON response") from exc

    if payload.get("ok") is not True:
        raise RuntimeError(f"External schedule push response did not confirm success: {payload}")

    logger.info(
        "External schedule pushed | shop_id=%s order_id=%s scheduled_date=%s updated=%s",
        normalized_shop_id,
        normalized_order_id,
        normalized_scheduled_date,
        payload.get("updated"),
    )
    return {"status": "sent", "updated": payload.get("updated")}
