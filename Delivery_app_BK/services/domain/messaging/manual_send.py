from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.order_events import OrderEvent


# Event name used for order events created by a manual send request. It is
# intentionally kept out of the OrderEvent enum: that enum drives
# MessageTemplate.validate_event, and a manual send is not a template-selectable
# business event. No handler is registered for it, so the event bus never fans
# it out to the automatic email/SMS handlers.
MANUAL_MESSAGE_EVENT_NAME = "order_manual_message"

# Marks every action produced by a manual send, so history consumers can tell
# manual sends apart from the automatic ones.
MANUAL_ACTION_SCOPE = "manual"

# MessageTemplate.ALLOWED_CHANNELS also accepts whatsapp/telegram, but no sender
# task exists for them, so they cannot be manually dispatched.
MANUAL_SENDABLE_CHANNELS = ("email", "sms")

MAX_MANUAL_TARGET_ORDERS = 100


def build_manual_action_name(template_event: str, channel: str) -> str:
    """
    Action names keep the "_email"/"_sms" suffix because the dispatcher resolves
    the sender task from that suffix (see events/action_dispatch.py).
    """
    return f"manual_{template_event}_{channel}"


def validate_manual_target_orders(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValidationFailed("order_ids must be a non-empty list of order ids.")

    order_ids: list[int] = []
    for raw_id in value:
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            raise ValidationFailed("order_ids must contain integer order ids only.")
        if raw_id not in order_ids:
            order_ids.append(raw_id)

    if len(order_ids) > MAX_MANUAL_TARGET_ORDERS:
        raise ValidationFailed(
            f"A manual send targets at most {MAX_MANUAL_TARGET_ORDERS} orders per request."
        )

    return order_ids


def validate_manual_template_event(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationFailed("event is required.")

    event_name = value.strip()
    if event_name not in OrderEvent._value2member_map_:
        raise ValidationFailed(
            f"Invalid event '{event_name}'. Allowed events: {[event.value for event in OrderEvent]}"
        )

    return event_name


def validate_manual_channels(value: Any) -> list[str]:
    if value is None:
        return list(MANUAL_SENDABLE_CHANNELS)

    if not isinstance(value, list) or not value:
        raise ValidationFailed(
            f"channels must be a non-empty list. Allowed channels: {list(MANUAL_SENDABLE_CHANNELS)}."
        )

    channels: list[str] = []
    for raw_channel in value:
        if not isinstance(raw_channel, str) or raw_channel.strip() not in MANUAL_SENDABLE_CHANNELS:
            raise ValidationFailed(
                f"Invalid channel '{raw_channel}'. Allowed channels: {list(MANUAL_SENDABLE_CHANNELS)}."
            )
        channel = raw_channel.strip()
        if channel not in channels:
            channels.append(channel)

    return channels


def validate_manual_source_event_id(value: Any, order_ids: list[int]) -> int | None:
    if value is None:
        return None

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationFailed("source_event_id must be an integer order event id.")

    if len(order_ids) != 1:
        raise ValidationFailed(
            "source_event_id can only be used when a single order is targeted."
        )

    return value
