from types import SimpleNamespace

import pytest

from Delivery_app_BK.services.domain.messaging import MANUAL_ACTION_SCOPE
from Delivery_app_BK.services.infra.events import realtime_refresh
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ORDER_MESSAGE_DISPATCHED,
    BUSINESS_EVENT_ORDER_MESSAGE_UPDATED,
)
from Delivery_app_BK.sockets.emitters import order_message_events


def _manual_action(**overrides):
    action = SimpleNamespace(
        id=40113,
        event_id=9912,
        team_id=7,
        action_scope=MANUAL_ACTION_SCOPE,
        status="FAILED",
        last_error="Order has no client email",
        processed_at=None,
        payload={
            "request_id": "b3f1",
            "template_event": "order_ready",
            "channel": "email",
        },
        event=SimpleNamespace(order_id=12, team_id=7, event_name="order_manual_message"),
    )
    for key, value in overrides.items():
        setattr(action, key, value)
    return action


# --- routing: manual sends bypass the relay, automatic ones keep it -----------


def test_manual_action_emits_a_message_frame_and_skips_the_relay(monkeypatch):
    emitted, relayed = [], []
    monkeypatch.setattr(
        order_message_events, "emit_order_message_updated",
        lambda **kwargs: emitted.append(kwargs),
    )
    monkeypatch.setattr(
        realtime_refresh, "notify_order_event_history_changed",
        lambda event_id: relayed.append(event_id),
    )

    realtime_refresh.notify_order_action_changed(_manual_action())

    assert relayed == []
    assert emitted == [{
        "team_id": 7,
        "order_id": 12,
        "event_id": 9912,
        "action_id": 40113,
        "request_id": "b3f1",
        "template_event": "order_ready",
        "channel": "email",
        "status": "FAILED",
        "last_error": "Order has no client email",
        "processed_at": None,
    }]


def test_automatic_action_still_uses_the_relay(monkeypatch):
    emitted, relayed = [], []
    monkeypatch.setattr(
        order_message_events, "emit_order_message_updated",
        lambda **kwargs: emitted.append(kwargs),
    )
    monkeypatch.setattr(
        realtime_refresh, "notify_order_event_history_changed",
        lambda event_id: relayed.append(event_id),
    )

    realtime_refresh.notify_order_action_changed(
        _manual_action(action_scope="", payload=None)
    )

    assert emitted == []
    assert relayed == [9912]


def test_manual_action_without_team_context_emits_nothing(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        order_message_events, "emit_order_message_updated",
        lambda **kwargs: emitted.append(kwargs),
    )

    action = _manual_action(team_id=None, event=SimpleNamespace(order_id=12, team_id=None))
    realtime_refresh.notify_order_action_changed(action)

    assert emitted == []


def test_processed_at_is_serialized_as_iso(monkeypatch):
    from datetime import datetime, timezone

    emitted = []
    monkeypatch.setattr(
        order_message_events, "emit_order_message_updated",
        lambda **kwargs: emitted.append(kwargs),
    )

    stamp = datetime(2026, 7, 24, 11, 2, 31, tzinfo=timezone.utc)
    realtime_refresh.notify_order_action_changed(
        _manual_action(status="SUCCESS", last_error=None, processed_at=stamp)
    )

    assert emitted[0]["processed_at"] == stamp.isoformat()


# --- envelope shape ----------------------------------------------------------


@pytest.fixture
def captured(monkeypatch):
    frames = []
    monkeypatch.setattr(
        order_message_events, "emit_business_event",
        lambda *, room, envelope: frames.append((room, envelope)),
    )
    return frames


def test_updated_frame_is_admin_scoped_and_carries_its_own_preview(captured):
    order_message_events.emit_order_message_updated(
        team_id=7, order_id=12, event_id=9912, action_id=40113,
        request_id="b3f1", template_event="order_ready", channel="email",
        status="SUCCESS", last_error=None, processed_at=None,
    )

    room, envelope = captured[0]
    assert room == "team:7:admin"
    assert envelope["event_name"] == BUSINESS_EVENT_ORDER_MESSAGE_UPDATED
    assert envelope["app_scopes"] == ["admin"]
    assert envelope["entity_type"] == "order"
    assert envelope["entity_id"] == 12
    # Present so emit_business_event does not build one, which would cost a
    # database read per frame.
    assert envelope["payload"]["notification_preview"]["title"] == "Message sent"
    assert envelope["payload"]["status"] == "SUCCESS"
    assert envelope["payload"]["request_id"] == "b3f1"


def test_dispatched_frame_counts_actions_and_lists_missing_orders(captured):
    order_message_events.emit_order_message_dispatched(
        team_id=7, request_id="b3f1", template_event="order_ready",
        channels=["email", "sms"], requested_by=41,
        orders=[
            {"order_id": 12, "event_id": 9912, "actions": [
                {"action_id": 1, "channel": "email", "status": "PENDING"},
                {"action_id": 2, "channel": "sms", "status": "PENDING"},
            ]},
            {"order_id": 15, "event_id": 9913, "actions": [
                {"action_id": 3, "channel": "email", "status": "PENDING"},
            ]},
        ],
        not_found_order_ids=[88],
    )

    room, envelope = captured[0]
    assert room == "team:7:admin"
    assert envelope["event_name"] == BUSINESS_EVENT_ORDER_MESSAGE_DISPATCHED
    assert envelope["app_scopes"] == ["admin"]
    assert envelope["entity_type"] == "order_message_request"
    assert envelope["entity_id"] is None
    assert envelope["payload"]["total_actions"] == 3
    assert envelope["payload"]["not_found_order_ids"] == [88]
    assert "notification_preview" in envelope["payload"]


def test_emit_failure_never_propagates(monkeypatch, captured):
    def _boom(*, room, envelope):
        raise RuntimeError("socket down")

    monkeypatch.setattr(order_message_events, "emit_business_event", _boom)
    monkeypatch.setattr(
        order_message_events, "current_app",
        SimpleNamespace(logger=SimpleNamespace(warning=lambda *a, **k: None)),
    )

    # The message is already sent by the time the frame goes out; a socket
    # failure must not flip the action to FAILED.
    order_message_events.emit_order_message_updated(
        team_id=7, order_id=12, event_id=9912, action_id=40113,
        request_id=None, template_event="order_ready", channel="sms",
        status="SUCCESS", last_error=None, processed_at=None,
    )
