from types import SimpleNamespace

from Delivery_app_BK.services.infra.events.handlers.order import order_shopify as module


def test_sync_shopify_fulfillment_on_order_completed_enqueues_job(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, external_source="shopify", external_order_id="12345")

    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.sync_shopify_fulfillment_on_order_completed(
        SimpleNamespace(order=order, order_id=18),
    )

    assert len(calls) == 1
    assert calls[0]["queue_key"] == "default"
    assert calls[0]["args"] == (18,)
    assert calls[0]["description"] == "fulfill-shopify-order:18"


def test_sync_shopify_fulfillment_on_order_completed_skips_non_shopify_orders(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, external_source="manual", external_order_id=None)

    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.sync_shopify_fulfillment_on_order_completed(
        SimpleNamespace(order=order, order_id=18),
    )

    assert calls == []


def test_notify_schedule_targets_on_order_created_enqueues_one_job_per_active_target(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, team_id=7, external_order_id="12345")
    plan = SimpleNamespace(start_date=SimpleNamespace(date=lambda: SimpleNamespace(isoformat=lambda: "2026-04-25")))
    targets = [SimpleNamespace(id=3), SimpleNamespace(id=4)]
    order_event = SimpleNamespace(order_id=18, payload={"delivery_plan_id": 11})

    def _fake_get(model, value):
        if getattr(model, "__name__", None) == "Order" and value == 18:
            return order
        if getattr(model, "__name__", None) == "RoutePlan" and value == 11:
            return plan
        return None

    monkeypatch.setattr(module.db.session, "get", _fake_get)
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(all=lambda: targets)
        ),
    )
    monkeypatch.setattr(
        module,
        "run_immediate_action",
        lambda order_event_arg, action_name, runner, **kwargs: calls.append(
            {
                "order_event": order_event_arg,
                "action_name": action_name,
                "runner": runner,
                **kwargs,
            }
        ),
    )

    module.notify_schedule_targets_on_order_created(order_event)

    assert len(calls) == 2
    assert calls[0]["order_event"] is order_event
    assert calls[0]["action_name"] == "order_schedule_notify"
    assert calls[0]["action_scope"] == "target:3"
    assert calls[0]["payload"] == {"target_id": 3, "scheduled_date": "2026-04-25"}
    assert calls[1]["action_scope"] == "target:4"
    assert calls[1]["payload"] == {"target_id": 4, "scheduled_date": "2026-04-25"}


def test_notify_schedule_targets_on_order_created_skips_when_plan_missing_date(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, team_id=7, external_order_id="12345")
    plan = SimpleNamespace(start_date=None)

    def _fake_get(model, value):
        if getattr(model, "__name__", None) == "Order" and value == 18:
            return order
        if getattr(model, "__name__", None) == "RoutePlan" and value == 11:
            return plan
        return None

    monkeypatch.setattr(module.db.session, "get", _fake_get)
    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.notify_schedule_targets_on_order_created(
        SimpleNamespace(order_id=18, payload={"delivery_plan_id": 11}),
    )

    assert calls == []


def test_notify_schedule_targets_on_delivery_rescheduled_uses_new_plan_start_date(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, team_id=7, external_order_id="12345")
    targets = [SimpleNamespace(id=3)]
    order_event = SimpleNamespace(order_id=18, payload={"new_plan_start": "2026-04-26T00:00:00+00:00"})

    monkeypatch.setattr(module.db.session, "get", lambda model, value: order if value == 18 else None)
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(all=lambda: targets)
        ),
    )
    monkeypatch.setattr(
        module,
        "run_immediate_action",
        lambda order_event_arg, action_name, runner, **kwargs: calls.append(
            {
                "order_event": order_event_arg,
                "action_name": action_name,
                "runner": runner,
                **kwargs,
            }
        ),
    )

    module.notify_schedule_targets_on_delivery_rescheduled(order_event)

    assert len(calls) == 1
    assert calls[0]["order_event"] is order_event
    assert calls[0]["action_name"] == "order_schedule_notify"
    assert calls[0]["action_scope"] == "target:3"
    assert calls[0]["payload"] == {"target_id": 3, "scheduled_date": "2026-04-26"}


def test_notify_schedule_targets_on_delivery_rescheduled_skips_non_external_orders(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, team_id=7, external_order_id=None)

    monkeypatch.setattr(module.db.session, "get", lambda model, value: order if value == 18 else None)
    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.notify_schedule_targets_on_delivery_rescheduled(
        SimpleNamespace(order_id=18, payload={"new_plan_start": "2026-04-26T00:00:00+00:00"}),
    )

    assert calls == []
