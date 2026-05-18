import importlib
from types import SimpleNamespace


module = importlib.import_module(
    "Delivery_app_BK.services.infra.tasks.order.push_external_schedule_action"
)


def test_push_external_schedule_action_marks_success(monkeypatch):
    route_plan = SimpleNamespace(start_date=SimpleNamespace(date=lambda: SimpleNamespace(isoformat=lambda: "2026-05-10")))
    team = SimpleNamespace(client_id="cl123")
    order = SimpleNamespace(
        external_source="shopify",
        external_order_id="987654321",
        route_plan=route_plan,
        route_plan_id=12,
        team=team,
        team_id=7,
    )
    action = SimpleNamespace(
        id=9,
        status="PENDING",
        scheduled_for=None,
        attempts=0,
        event=SimpleNamespace(order=order),
        event_id=7,
        last_error=None,
        processed_at=None,
    )
    realtime_calls: list[int] = []
    pushes: list[dict] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: action if value == 9 else None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "notify_order_event_history_changed", lambda event_id: realtime_calls.append(event_id))
    monkeypatch.setattr(
        module,
        "push_order_schedule_update",
        lambda **kwargs: pushes.append(kwargs) or {"status": "sent", "updated": 1},
    )

    module.push_external_schedule_action(9)

    assert action.status == "SUCCESS"
    assert action.attempts == 1
    assert action.last_error is None
    assert action.processed_at is not None
    assert pushes == [
        {
            "shop_id": "cl123",
            "order_id": "987654321",
            "scheduled_date": "2026-05-10",
        }
    ]
    assert realtime_calls[-1] == 7


def test_push_external_schedule_action_sends_empty_date_when_unassigned(monkeypatch):
    team = SimpleNamespace(client_id="cl123")
    order = SimpleNamespace(
        external_source="shopify",
        external_order_id="987654321",
        route_plan=None,
        route_plan_id=None,
        team=team,
        team_id=7,
    )
    action = SimpleNamespace(
        id=9,
        status="PENDING",
        scheduled_for=None,
        attempts=0,
        event=SimpleNamespace(order=order),
        event_id=7,
        last_error=None,
        processed_at=None,
    )
    pushes: list[dict] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: action if value == 9 else None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "notify_order_event_history_changed", lambda _event_id: None)
    monkeypatch.setattr(
        module,
        "push_order_schedule_update",
        lambda **kwargs: pushes.append(kwargs) or {"status": "sent", "updated": 1},
    )

    module.push_external_schedule_action(9)

    assert action.status == "SUCCESS"
    assert pushes[0]["scheduled_date"] == ""


def test_push_external_schedule_action_marks_skipped_for_non_shopify(monkeypatch):
    order = SimpleNamespace(
        external_source="manual",
        external_order_id="987654321",
        route_plan=None,
        route_plan_id=None,
        team=SimpleNamespace(client_id="cl123"),
        team_id=7,
    )
    action = SimpleNamespace(
        id=9,
        status="PENDING",
        scheduled_for=None,
        attempts=0,
        event=SimpleNamespace(order=order),
        event_id=7,
        last_error=None,
        processed_at=None,
    )

    monkeypatch.setattr(module.db.session, "get", lambda model, value: action if value == 9 else None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "notify_order_event_history_changed", lambda _event_id: None)

    module.push_external_schedule_action(9)

    assert action.status == "SKIPPED"
    assert action.last_error == "Order is not a Shopify external order"
