import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.messaging.manual_send import (
    MANUAL_MESSAGE_EVENT_NAME,
    MANUAL_SENDABLE_CHANNELS,
    MAX_MANUAL_TARGET_ORDERS,
    build_manual_action_name,
    validate_manual_channels,
    validate_manual_source_event_id,
    validate_manual_target_orders,
    validate_manual_template_event,
)
from Delivery_app_BK.services.domain.order.order_events import OrderEvent


def test_manual_event_name_is_not_a_template_selectable_event():
    # The manual event must stay out of the OrderEvent enum, otherwise
    # MessageTemplate.validate_event would offer it as a template event.
    assert MANUAL_MESSAGE_EVENT_NAME not in OrderEvent._value2member_map_


@pytest.mark.parametrize("channel", MANUAL_SENDABLE_CHANNELS)
def test_action_name_keeps_the_channel_suffix_the_dispatcher_routes_on(channel):
    from Delivery_app_BK.services.infra.events.action_dispatch import _resolve_order_action_task
    from Delivery_app_BK.services.infra.tasks.order.send_email import send_email
    from Delivery_app_BK.services.infra.tasks.order.send_sms import send_sms

    expected_task = send_sms if channel == "sms" else send_email
    action_name = build_manual_action_name(OrderEvent.READY.value, channel)

    assert action_name.endswith(f"_{channel}")
    assert _resolve_order_action_task(action_name) is expected_task


def test_target_orders_are_deduplicated_and_order_preserved():
    assert validate_manual_target_orders([7, 3, 7, 9]) == [7, 3, 9]


@pytest.mark.parametrize("value", [None, [], "12", [12, "13"], [12, True]])
def test_invalid_target_orders_are_rejected(value):
    with pytest.raises(ValidationFailed):
        validate_manual_target_orders(value)


def test_target_orders_are_capped():
    with pytest.raises(ValidationFailed):
        validate_manual_target_orders(list(range(MAX_MANUAL_TARGET_ORDERS + 1)))


def test_template_event_must_be_a_known_order_event():
    assert validate_manual_template_event(" order_ready ") == OrderEvent.READY.value

    with pytest.raises(ValidationFailed):
        validate_manual_template_event("order_not_a_real_event")


def test_channels_default_to_every_sendable_channel():
    assert validate_manual_channels(None) == list(MANUAL_SENDABLE_CHANNELS)
    assert validate_manual_channels(["sms", "sms"]) == ["sms"]


@pytest.mark.parametrize("value", ["email", [], ["whatsapp"], ["telegram"]])
def test_channels_without_a_sender_task_are_rejected(value):
    with pytest.raises(ValidationFailed):
        validate_manual_channels(value)


def test_source_event_is_optional_and_single_order_only():
    assert validate_manual_source_event_id(None, [1, 2]) is None
    assert validate_manual_source_event_id(883, [1]) == 883

    with pytest.raises(ValidationFailed):
        validate_manual_source_event_id(883, [1, 2])

    with pytest.raises(ValidationFailed):
        validate_manual_source_event_id("883", [1])
