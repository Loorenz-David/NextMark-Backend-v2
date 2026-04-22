import importlib
from types import SimpleNamespace


module = importlib.import_module(
    "Delivery_app_BK.services.infra.tasks.order.notify_order_schedule_action"
)


def test_notify_order_schedule_action_marks_success(monkeypatch):
    action = SimpleNamespace(
        id=9,
        status="PENDING",
        scheduled_for=None,
        attempts=0,
        payload={"target_id": 3, "scheduled_date": "2026-04-25"},
        event=SimpleNamespace(order=SimpleNamespace(id=19), event_id=7),
        event_id=7,
        last_error=None,
        processed_at=None,
    )
    commit_calls: list[str] = []
    realtime_calls: list[int] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: action if value == 9 else None)
    monkeypatch.setattr(module.db.session, "commit", lambda: commit_calls.append("commit"))
    monkeypatch.setattr(module, "notify_order_event_history_changed", lambda event_id: realtime_calls.append(event_id))
    monkeypatch.setattr(module, "notify_order_schedule", lambda *args: {"status": "sent"})

    module.notify_order_schedule_action(9)

    assert action.status == "SUCCESS"
    assert action.attempts == 1
    assert action.last_error is None
    assert action.processed_at is not None
    assert realtime_calls[-1] == 7


def test_notify_order_schedule_action_marks_skipped(monkeypatch):
    action = SimpleNamespace(
        id=9,
        status="PENDING",
        scheduled_for=None,
        attempts=0,
        payload={"target_id": 3, "scheduled_date": "2026-04-25"},
        event=SimpleNamespace(order=SimpleNamespace(id=19), event_id=7),
        event_id=7,
        last_error=None,
        processed_at=None,
    )
    realtime_calls: list[int] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: action if value == 9 else None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "notify_order_event_history_changed", lambda event_id: realtime_calls.append(event_id))
    monkeypatch.setattr(
        module,
        "notify_order_schedule",
        lambda *args: {"status": "skipped", "reason": "Schedule target is missing or inactive"},
    )

    module.notify_order_schedule_action(9)

    assert action.status == "SKIPPED"
    assert action.attempts == 1
    assert action.last_error == "Schedule target is missing or inactive"
    assert action.processed_at is not None
    assert realtime_calls[-1] == 7
