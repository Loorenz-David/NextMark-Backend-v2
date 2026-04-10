from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.order_states import (
    update_orders_state as module,
)
from Delivery_app_BK.services.queries.order.serialize_state_update import (
    build_order_state_update_payload,
)


class _DummyTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_update_orders_state_updates_and_emits(monkeypatch):
    state_instance = SimpleNamespace(id=4, name="Ready")
    order = SimpleNamespace(
        id=11,
        team_id=7,
        order_state_id=2,
        route_group=SimpleNamespace(id=9, route_solutions=[], orders=[], state_id=1),
        route_group_id=9,
        route_plan=None,
        delivery_plan=None,
    )
    emitted = []

    monkeypatch.setattr(module, "get_instance", lambda ctx, model, value: state_instance)
    monkeypatch.setattr(module, "_resolve_orders", lambda ctx, orders: [order])
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())
    monkeypatch.setattr(
        module,
        "emit_order_events",
        lambda ctx, events: emitted.extend(events),
    )

    updated_orders = module.update_orders_state(
        ctx=SimpleNamespace(),
        orders=11,
        state_id=4,
    )

    assert order.order_state_id == 4
    assert len(updated_orders) == 1
    assert len(emitted) == 2


def test_update_orders_state_skips_unchanged_without_emitting(monkeypatch):
    state_instance = SimpleNamespace(id=4, name="Ready")
    order = SimpleNamespace(id=11, team_id=7, order_state_id=4)
    emitted = []

    monkeypatch.setattr(module, "get_instance", lambda ctx, model, value: state_instance)
    monkeypatch.setattr(module, "_resolve_orders", lambda ctx, orders: [order])
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())
    monkeypatch.setattr(
        module,
        "emit_order_events",
        lambda ctx, events: emitted.extend(events),
    )

    updated_orders = module.update_orders_state(
        ctx=SimpleNamespace(),
        orders=11,
        state_id=4,
    )

    assert updated_orders == []
    assert emitted == []


def test_update_orders_state_appends_failure_note_when_target_state_is_fail(monkeypatch):
    state_instance = SimpleNamespace(id=8, name="Fail")
    order = SimpleNamespace(
        id=11,
        team_id=7,
        order_state_id=2,
        order_notes=[{"type": "GENERAL", "content": "g"}],
        route_group=SimpleNamespace(id=9, route_solutions=[], orders=[], state_id=1),
        route_group_id=9,
        route_plan=None,
        delivery_plan=None,
    )

    monkeypatch.setattr(module, "get_instance", lambda ctx, model, value: state_instance)
    monkeypatch.setattr(module, "_resolve_orders", lambda ctx, orders: [order])
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)

    module.update_orders_state(
        ctx=SimpleNamespace(
            incoming_data={
                "order_notes": {
                    "type": "FAILURE",
                    "content": "delivery attempt failed",
                }
            }
        ),
        orders=11,
        state_id=8,
    )

    assert len(order.order_notes) == 2
    assert order.order_notes[0] == {"type": "GENERAL", "content": "g"}
    assert order.order_notes[1]["type"] == "FAILURE"
    assert order.order_notes[1]["content"] == "delivery attempt failed"
    assert isinstance(order.order_notes[1]["creation_date"], str)


def test_update_orders_state_rejects_non_failure_note_type_in_payload(monkeypatch):
    state_instance = SimpleNamespace(id=8, name="Fail")
    order = SimpleNamespace(id=11, team_id=7, order_state_id=2)

    monkeypatch.setattr(module, "get_instance", lambda ctx, model, value: state_instance)
    monkeypatch.setattr(module, "_resolve_orders", lambda ctx, orders: [order])
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)

    with pytest.raises(ValidationFailed):
        module.update_orders_state(
            ctx=SimpleNamespace(
                incoming_data={
                    "order_notes": {
                        "type": "GENERAL",
                        "content": "not allowed here",
                    }
                }
            ),
            orders=11,
            state_id=8,
        )


def test_update_orders_state_appends_failure_note_from_fields_payload(monkeypatch):
    state_instance = SimpleNamespace(id=8, name="Fail")
    order = SimpleNamespace(
        id=11,
        team_id=7,
        order_state_id=2,
        order_notes=[],
        route_group=SimpleNamespace(id=9, route_solutions=[], orders=[], state_id=1),
        route_group_id=9,
        route_plan=None,
        delivery_plan=None,
    )

    monkeypatch.setattr(module, "get_instance", lambda ctx, model, value: state_instance)
    monkeypatch.setattr(module, "_resolve_orders", lambda ctx, orders: [order])
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)

    module.update_orders_state(
        ctx=SimpleNamespace(
            incoming_data={
                "fields": {
                    "order_notes": {
                        "type": "FAILURE",
                        "content": "Vehicle breakdown delayed delivery.",
                    }
                }
            }
        ),
        orders=11,
        state_id=8,
    )

    assert len(order.order_notes) == 1
    assert order.order_notes[0]["type"] == "FAILURE"
    assert order.order_notes[0]["content"] == "Vehicle breakdown delayed delivery."
    assert isinstance(order.order_notes[0]["creation_date"], str)


def test_recompute_and_auto_complete_plans_runs_group_and_plan_sync(monkeypatch):
    route_group = SimpleNamespace(id=9, route_solutions=[])
    plan = SimpleNamespace(id=3)
    order = SimpleNamespace(
        id=11,
        delivery_plan=plan,
        route_group=route_group,
        route_group_id=9,
    )

    calls = {
        "recompute": 0,
        "auto": 0,
        "group_recompute": 0,
        "group_sync": 0,
        "plan_sync": 0,
    }

    monkeypatch.setattr(
        module,
        "recompute_plan_order_counts",
        lambda _plan: calls.__setitem__("recompute", calls["recompute"] + 1),
    )
    monkeypatch.setattr(
        module,
        "maybe_auto_complete_plan",
        lambda _plan: calls.__setitem__("auto", calls["auto"] + 1),
    )
    monkeypatch.setattr(
        module,
        "recompute_route_group_order_counts",
        lambda _solution: calls.__setitem__("group_recompute", calls["group_recompute"] + 1),
    )
    monkeypatch.setattr(
        module,
        "maybe_sync_route_group_state",
        lambda _group: calls.__setitem__("group_sync", calls["group_sync"] + 1),
    )
    monkeypatch.setattr(
        module,
        "maybe_sync_plan_state_from_groups",
        lambda _plan: calls.__setitem__("plan_sync", calls["plan_sync"] + 1),
    )

    module._recompute_and_auto_complete_plans([order])

    assert calls == {
        "recompute": 1,
        "auto": 1,
        "group_recompute": 0,
        "group_sync": 1,
        "plan_sync": 1,
    }


def test_recompute_and_auto_complete_plans_resolves_group_from_plan_when_missing_direct_ref(monkeypatch):
    route_group = SimpleNamespace(id=9, route_solutions=[])
    plan = SimpleNamespace(id=3, route_groups=[route_group])
    order = SimpleNamespace(
        id=11,
        delivery_plan=plan,
        route_group=None,
        route_group_id=9,
    )

    group_synced = []
    monkeypatch.setattr(module, "recompute_plan_order_counts", lambda _plan: None)
    monkeypatch.setattr(module, "maybe_auto_complete_plan", lambda _plan: None)
    monkeypatch.setattr(module, "recompute_route_group_order_counts", lambda _solution: None)
    monkeypatch.setattr(module, "maybe_sync_plan_state_from_groups", lambda _plan: None)
    monkeypatch.setattr(
        module,
        "maybe_sync_route_group_state",
        lambda group: group_synced.append(group.id),
    )

    module._recompute_and_auto_complete_plans([order])

    assert group_synced == [9]


def test_update_orders_state_payload_wraps_changed_orders(monkeypatch):
    payload = {"orders": [{"id": 11}], "route_groups": [], "route_plans": []}

    monkeypatch.setattr(module, "update_orders_state", lambda **_kwargs: [SimpleNamespace(id=11)])
    monkeypatch.setattr(module, "build_order_state_update_payload", lambda changed: payload)

    result = module.update_orders_state_payload(
        ctx=SimpleNamespace(),
        orders=11,
        state_id=4,
    )

    assert result == payload


def test_build_order_state_update_payload_serializes_orders_groups_and_plans(monkeypatch):
    route_group = SimpleNamespace(
        id=9,
        client_id="rg_9",
        route_plan_id=3,
        state_id=4,
        total_orders=1,
        order_state_counts={"Ready": 1},
    )
    route_plan = SimpleNamespace(
        id=3,
        client_id="rp_3",
        state_id=4,
        total_orders=1,
    )
    order = SimpleNamespace(
        id=11,
        client_id="ord_11",
        order_state_id=4,
        route_group_id=9,
        route_plan_id=3,
    )

    monkeypatch.setattr(
        "Delivery_app_BK.services.queries.order.serialize_state_update._load_route_groups_by_ids",
        lambda ids: [route_group] if ids == {9} else [],
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.queries.order.serialize_state_update._load_route_plans_by_ids",
        lambda ids: [route_plan] if ids == {3} else [],
    )

    result = build_order_state_update_payload([order])

    assert result == {
        "orders": [
            {
                "id": 11,
                "client_id": "ord_11",
                "order_state_id": 4,
                "route_group_id": 9,
                "route_plan_id": 3,
            }
        ],
        "route_groups": [
            {
                "id": 9,
                "client_id": "rg_9",
                "route_plan_id": 3,
                "state_id": 4,
                "total_orders": 1,
                "order_state_counts": {"Ready": 1},
            }
        ],
        "route_plans": [
            {
                "id": 3,
                "client_id": "rp_3",
                "state_id": 4,
                "total_orders": 1,
            }
        ],
    }
