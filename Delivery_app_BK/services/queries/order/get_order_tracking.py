"""
Public order tracking query.

Security:
- Incoming raw token is SHA-256 hashed before DB lookup.
- Returns only a customer-safe DTO — no driver, plan, team IDs, or admin data.

Usage:
    from Delivery_app_BK.services.queries.order.get_order_tracking import get_order_tracking
    data = get_order_tracking(raw_token)
"""

import hashlib
from datetime import timezone

from Delivery_app_BK.models import db, Order
from Delivery_app_BK.errors import NotFound


# ---------------------------------------------------------------------------
# Customer-visible event names (all others are filtered out).
# ---------------------------------------------------------------------------
CUSTOMER_SAFE_EVENTS = {
    "order_created",
    "order_confirmed",
    "order_preparing",
    "order_ready",
    "order_processing",
    "order_completed",
    "order_failed",
    "order_cancelled",
    "order_delivery_window_changed_by_user",
    "order_rescheduled",
}

EVENT_LABEL_MAP = {
    "order_created": "Order received",
    "order_confirmed": "Order confirmed",
    "order_preparing": "Preparing your order",
    "order_ready": "Ready",
    "order_processing": "On the way",
    "order_completed": "Delivered",
    "order_failed": "Delivery issue",
    "order_cancelled": "Order cancelled",
    "order_delivery_window_changed_by_user": "Schedule updated",
    "order_rescheduled": "Schedule updated",
}


def _build_timeline(events) -> list[dict]:
    """Filter, sort, deduplicate, and format order events into a timeline."""
    # 1. Keep only customer-safe events.
    safe = [e for e in events if e.event_name in CUSTOMER_SAFE_EVENTS]

    # 2. Sort chronologically (oldest first).
    safe.sort(key=lambda e: e.occurred_at)

    # 3. Deduplicate: skip an event if it is the same type as the immediately
    #    preceding entry in the timeline (consecutive duplicates).
    #    This handles the case where order creation and a rapid state change
    #    both emit the same event name (e.g. two order_confirmed rows), while
    #    still allowing the same event to appear again after a different event
    #    in between (e.g. confirmed → cancelled → confirmed on a re-open).
    timeline: list[dict] = []

    for event in safe:
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        # Skip if this event is the same as the last one appended.
        if timeline and timeline[-1]["event_name"] == event.event_name:
            continue

        timeline.append(
            {
                "event_name": event.event_name,
                "label": EVENT_LABEL_MAP.get(event.event_name, event.event_name),
                "occurred_at": occurred_at.isoformat(),
            }
        )

    return timeline


def get_order_tracking(token: str) -> dict:
    """Look up an order by its raw tracking token and return a customer-safe DTO.

    Args:
        token: The raw (unhashed) tracking token from the URL.

    Returns:
        A dict matching the public tracking DTO shape.

    Raises:
        NotFound: If no order matches the given token.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    order: Order | None = (
        db.session.query(Order)
        .filter(Order.tracking_token_hash == token_hash)
        .first()
    )

    if order is None:
        raise NotFound("Order not found.")

    # ── Timeline ───────────────────────────────────────────────────────────
    timeline = _build_timeline(order.events or [])
    current_status_label = timeline[-1]["label"] if timeline else None

    # ── Current status ─────────────────────────────────────────────────────
    current_status: str | None = None
    if order.state is not None:
        current_status = order.state.name

    # ── Team info ──────────────────────────────────────────────────────────
    team_name: str = ""
    team_timezone: str | None = None
    if order.team is not None:
        team_name = order.team.name or ""
        team_timezone = getattr(order.team, "time_zone", None)

    # ── Delivery window summary (first window only) ────────────────────────
    delivery_window_summary: dict | None = None
    if order.delivery_windows:
        first_window = order.delivery_windows[0]
        start_at = first_window.start_at
        end_at = first_window.end_at
        if start_at is not None and start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        if end_at is not None and end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        delivery_window_summary = {
            "start_at": start_at.isoformat() if start_at else None,
            "end_at": end_at.isoformat() if end_at else None,
        }

    return {
        "tracking_number": order.tracking_number,
        "reference_number": order.order_scalar_id or order.reference_number or None,
        "team_name": team_name,
        "team_timezone": team_timezone,
        "current_status": current_status,
        "current_status_label": current_status_label,
        "delivery_window_summary": delivery_window_summary,
        "timeline": timeline,
    }
