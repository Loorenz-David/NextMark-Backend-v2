from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.messaging import send_manual_message as module
from Delivery_app_BK.services.context import ServiceContext


IDENTITY = {"active_team_id": 7, "user_id": 3}


def _order(order_id: int, plan_type: str) -> SimpleNamespace:
    return SimpleNamespace(id=order_id, route_plan=SimpleNamespace(plan_type=plan_type), order_plan_objective=None)


def _install(monkeypatch, *, orders: dict[int, SimpleNamespace], templates: dict[tuple[str, str], object]):
    """
    `templates` maps (plan_type, channel) -> enabled template; anything else
    resolves to None, which is how the resolver reports a missing/disabled one.
    """
    captured = {"resolve": [], "emitted_order_ids": [], "actions": [], "frame": None, "enqueued": []}

    monkeypatch.setattr(module, "_load_orders", lambda *, order_ids, team_id: orders)

    def _resolve(**kwargs):
        captured["resolve"].append(kwargs)
        return templates.get((kwargs["plan_type"], kwargs["channel"]))

    monkeypatch.setattr(module, "resolve_message_template", _resolve)
    monkeypatch.setattr(module, "_resolve_source_events", lambda **_kwargs: {})

    def _emit_events(*, order_ids, **_kwargs):
        captured["emitted_order_ids"] = list(order_ids)
        return {order_id: SimpleNamespace(id=1000 + order_id, order_id=order_id) for order_id in order_ids}

    monkeypatch.setattr(module, "_emit_manual_events", _emit_events)

    next_action_id = iter(range(500, 600))

    def _create_action(**kwargs):
        action = SimpleNamespace(
            id=next(next_action_id),
            payload={"channel": kwargs["channel"], "plan_type": kwargs["plan_type"]},
            attempts=0,
            status="PENDING",
            last_error=None,
        )
        captured["actions"].append(kwargs)
        return action

    monkeypatch.setattr(module, "_create_manual_action", _create_action)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "emit_order_message_dispatched", lambda **kwargs: captured.__setitem__("frame", kwargs))
    monkeypatch.setattr(module, "enqueue_order_action", lambda action: captured["enqueued"].append(action))
    return captured


def _ctx(order_ids, channels=("email", "sms")):
    return ServiceContext(
        incoming_data={"order_ids": list(order_ids), "event": "order_ready", "channels": list(channels)},
        identity=dict(IDENTITY),
    )


def test_mixed_batch_resolves_channels_per_order_plan_type(monkeypatch):
    orders = {10: _order(10, "store_pickup"), 11: _order(11, "local_delivery")}
    captured = _install(
        monkeypatch,
        orders=orders,
        templates={
            ("store_pickup", "sms"): object(),
            ("local_delivery", "sms"): object(),
            ("local_delivery", "email"): object(),
        },
    )

    outcome = module.send_manual_order_message(_ctx([10, 11]))

    by_order = {r["order_id"]: r for r in outcome["results"]}
    assert by_order[10]["plan_type"] == "store_pickup"
    assert by_order[10]["channels"]["sms"]["status"] == "queued"
    assert by_order[10]["channels"]["email"]["status"] == "skipped"
    assert "store_pickup" in by_order[10]["channels"]["email"]["detail"]
    assert by_order[11]["plan_type"] == "local_delivery"
    assert {c: r["status"] for c, r in by_order[11]["channels"].items()} == {"email": "queued", "sms": "queued"}

    assert outcome["plan_types"] == {"store_pickup": ["sms"], "local_delivery": ["email", "sms"]}
    assert outcome["channels"] == ["email", "sms"]
    # One resolver call per (plan type, channel), never per order.
    assert len(captured["resolve"]) == 4
    assert all(call["enabled_only"] is True for call in captured["resolve"])
    assert captured["frame"]["plan_types"] == outcome["plan_types"]
    assert captured["frame"]["skipped_orders"] == []
    assert len(captured["enqueued"]) == 3


def test_order_without_any_template_for_its_plan_type_is_skipped_without_an_event(monkeypatch):
    orders = {10: _order(10, "store_pickup"), 11: _order(11, "local_delivery")}
    captured = _install(monkeypatch, orders=orders, templates={("local_delivery", "email"): object()})

    outcome = module.send_manual_order_message(_ctx([10, 11, 99]))

    by_order = {r["order_id"]: r for r in outcome["results"]}
    assert by_order[10]["status"] == "skipped"
    assert by_order[10]["plan_type"] == "store_pickup"
    assert "store_pickup" in by_order[10]["detail"]
    assert by_order[11]["status"] == "accepted"
    assert by_order[99]["status"] == "not_found"

    # No manual event row for the skipped order: it would carry zero actions.
    assert captured["emitted_order_ids"] == [11]
    assert captured["frame"]["skipped_orders"] == [
        {"order_id": 10, "plan_type": "store_pickup", "detail": by_order[10]["detail"]}
    ]
    assert captured["frame"]["not_found_order_ids"] == [99]
    assert [o["order_id"] for o in captured["frame"]["orders"]] == [11]
    assert outcome["plan_types"] == {"store_pickup": [], "local_delivery": ["email"]}
    assert outcome["channels"] == ["email"]


def test_batch_with_no_sendable_order_is_rejected(monkeypatch):
    orders = {10: _order(10, "store_pickup")}
    _install(monkeypatch, orders=orders, templates={("local_delivery", "email"): object()})

    with pytest.raises(ValidationFailed, match="store_pickup"):
        module.send_manual_order_message(_ctx([10]))


def test_batch_where_nothing_was_found_still_reports_not_found(monkeypatch):
    captured = _install(monkeypatch, orders={}, templates={})

    outcome = module.send_manual_order_message(_ctx([42]))

    assert outcome["results"] == [{"order_id": 42, "status": "not_found"}]
    assert outcome["plan_types"] == {}
    assert captured["resolve"] == []


def test_manual_action_payload_records_the_plan_type(monkeypatch):
    orders = {10: _order(10, "international_shipping")}
    captured = _install(monkeypatch, orders=orders, templates={("international_shipping", "email"): object()})

    module.send_manual_order_message(_ctx([10], channels=("email",)))

    assert captured["actions"] == [
        {
            "manual_event": captured["actions"][0]["manual_event"],
            "team_id": 7,
            "request_id": captured["actions"][0]["request_id"],
            "template_event": "order_ready",
            "plan_type": "international_shipping",
            "channel": "email",
            "requested_by": 3,
            "source_event": None,
        }
    ]
