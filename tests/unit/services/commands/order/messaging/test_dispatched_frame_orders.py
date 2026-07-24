from types import SimpleNamespace

from Delivery_app_BK.services.commands.order.messaging import send_manual_message
from Delivery_app_BK.services.commands.order.messaging.send_manual_message import (
    _build_dispatched_frame_orders,
    _enqueue_prepared_actions,
)


RESULTS = [
    {
        "order_id": 12,
        "status": "accepted",
        "event_id": 9912,
        "source_event_id": None,
        "channels": {
            "email": {"status": "queued", "action_id": 40113},
            "sms": {"status": "skipped", "detail": "No enabled sms template for event 'order_ready'."},
        },
    },
    {
        "order_id": 15,
        "status": "accepted",
        "event_id": 9913,
        "source_event_id": None,
        "channels": {
            "email": {"status": "queued", "action_id": 40114},
        },
    },
    {"order_id": 88, "status": "not_found"},
]


def test_only_accepted_orders_reach_the_frame():
    frame_orders = _build_dispatched_frame_orders(RESULTS)

    assert [order["order_id"] for order in frame_orders] == [12, 15]


def test_skipped_channels_produce_no_action_entry():
    # A skipped channel never created an action row, so there is nothing for the
    # client to track; the request-level `channels` field covers that case.
    email_order = _build_dispatched_frame_orders(RESULTS)[0]

    assert email_order["event_id"] == 9912
    assert email_order["actions"] == [
        {"action_id": 40113, "channel": "email", "status": "PENDING"}
    ]


def test_every_action_in_the_frame_is_pending():
    # The frame is built before anything is queued, so no other status can occur.
    frame_orders = _build_dispatched_frame_orders(RESULTS)

    statuses = {a["status"] for order in frame_orders for a in order["actions"]}
    assert statuses == {"PENDING"}


def test_empty_results_produce_an_empty_frame():
    assert _build_dispatched_frame_orders([]) == []
    assert _build_dispatched_frame_orders([{"order_id": 1, "status": "not_found"}]) == []


# --- enqueue phase -----------------------------------------------------------


def _prepared(action):
    return {
        "actions": [action],
        "result": {
            "order_id": 12,
            "status": "accepted",
            "event_id": 9912,
            "channels": {"email": {"status": "queued", "action_id": action.id}},
        },
    }


def _action():
    return SimpleNamespace(
        id=40113, attempts=0, status="PENDING", last_error=None,
        payload={"channel": "email"},
    )


def test_successful_enqueue_leaves_the_result_queued(monkeypatch):
    notified = []
    monkeypatch.setattr(send_manual_message, "enqueue_order_action", lambda _a: None)
    monkeypatch.setattr(
        send_manual_message, "notify_order_action_changed", lambda a: notified.append(a)
    )

    prepared = _prepared(_action())
    _enqueue_prepared_actions(prepared)

    assert prepared["result"]["channels"]["email"]["status"] == "queued"
    assert notified == []


def test_enqueue_failure_marks_the_action_and_publishes_a_status_frame(monkeypatch):
    notified = []

    def _boom(_action):
        raise RuntimeError("redis down")

    monkeypatch.setattr(send_manual_message, "enqueue_order_action", _boom)
    monkeypatch.setattr(send_manual_message.db.session, "commit", lambda: None)
    monkeypatch.setattr(
        send_manual_message, "notify_order_action_changed", lambda a: notified.append(a)
    )

    action = _action()
    prepared = _prepared(action)
    _enqueue_prepared_actions(prepared)

    assert action.status == "FAILED"
    assert action.last_error == "redis down"
    assert action.attempts == 1
    assert prepared["result"]["channels"]["email"] == {
        "status": "failed", "action_id": 40113, "detail": "redis down",
    }
    # No worker will ever run for this action, so the PENDING state already
    # published in the dispatched frame must be corrected by a status frame.
    assert notified == [action]
