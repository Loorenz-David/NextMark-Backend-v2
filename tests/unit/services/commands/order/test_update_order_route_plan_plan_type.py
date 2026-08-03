from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order import update_order_route_plan as module


def _install_common_stubs(monkeypatch, *, order, old_plan, new_plan, plan_change_calls):
    monkeypatch.setattr(module, "_resolve_plan_instance", lambda *_a, **_k: new_plan)
    monkeypatch.setattr(module, "_resolve_orders_for_update", lambda *_a, **_k: {order.id: order})
    monkeypatch.setattr(module, "_get_order_route_plan_id", lambda i: i.route_plan_id)
    monkeypatch.setattr(module, "_get_order_route_group_id", lambda i: i.route_group_id)
    monkeypatch.setattr(
        module,
        "_set_order_route_plan_id",
        lambda i, v: setattr(i, "route_plan_id", v),
    )
    monkeypatch.setattr(
        module,
        "_set_order_route_group_id",
        lambda i, v: setattr(i, "route_group_id", v),
    )
    monkeypatch.setattr(
        module,
        "_load_route_plans_by_id",
        lambda *_a, **_k: ({old_plan.id: old_plan} if old_plan else {}),
    )
    monkeypatch.setattr(
        module,
        "build_plan_change_apply_context",
        lambda **_k: SimpleNamespace(
            source_route_group_id_by_order_id={},
            destination_route_group_id_by_order_id={},
        ),
    )
    monkeypatch.setattr(
        module,
        "_prepare_old_local_delivery_batch_changes",
        lambda **_k: {
            "order_ids": set(),
            "instances": [],
            "post_flush_actions": [],
            "updated_stops": [],
            "synced_stops": [],
            "updated_route_solutions": [],
            "synced_route_solutions": [],
        },
    )

    def _apply_order_plan_change(*, ctx, order_instance, old_plan, new_plan, apply_context):
        plan_change_calls.append(
            (getattr(old_plan, "id", None), getattr(new_plan, "id", None))
        )
        return SimpleNamespace(
            instances=[], post_flush_actions=[], serialize_bundle=lambda: {}
        )

    monkeypatch.setattr(module, "apply_order_plan_change", _apply_order_plan_change)
    monkeypatch.setattr(module, "_resolve_affected_route_groups", lambda **_k: [])
    monkeypatch.setattr(module, "_fetch_stop_eta_by_order_id", lambda *_a, **_k: {})
    monkeypatch.setattr(module, "build_route_plan_changed_event", lambda *_a, **_k: {})
    monkeypatch.setattr(module, "build_delivery_rescheduled_event", lambda *_a, **_k: {})
    monkeypatch.setattr(module, "_sanitize_instances_for_session", lambda i: i)
    monkeypatch.setattr(module, "touch_route_freshness", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "recompute_plan_totals", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "recompute_route_group_totals", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "recompute_plan_order_counts", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "_apply_move_state_heritage", lambda **_k: None)
    monkeypatch.setattr(module, "_transition_draft_orders_to_confirmed", lambda **_k: [])
    monkeypatch.setattr(module, "_serialize_old_local_delivery_batch_bundle", lambda **_k: {})
    monkeypatch.setattr(
        module,
        "_build_state_changes_bundle",
        lambda **_k: {"route_groups": [], "route_plans": []},
    )
    monkeypatch.setattr(
        module,
        "serialize_created_order",
        lambda i: {
            "id": i.id,
            "route_plan_id": i.route_plan_id,
            "route_group_id": i.route_group_id,
            "order_plan_objective": i.order_plan_objective,
        },
    )
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(
            session=SimpleNamespace(add_all=lambda *_a, **_k: None, flush=lambda: None)
        ),
    )


def _order():
    return SimpleNamespace(
        id=1,
        route_plan_id=10,
        route_group_id=20,
        order_plan_objective="local_delivery",
        order_state_id=3,
    )


def _plan(plan_id, plan_type):
    return SimpleNamespace(
        id=plan_id,
        plan_type=plan_type,
        route_groups=[],
        start_date=None,
        end_date=None,
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        total_orders=0,
    )


def test_moving_to_an_international_plan_adopts_its_objective_and_drops_the_route_group(
    monkeypatch,
):
    # Before plan_type existed this path hardcoded "local_delivery" and would have
    # raised looking for route groups the destination does not have.
    order = _order()
    old_plan = _plan(10, "local_delivery")
    new_plan = _plan(99, "international_shipping")
    plan_change_calls: list[tuple[int | None, int | None]] = []
    _install_common_stubs(
        monkeypatch,
        order=order,
        old_plan=old_plan,
        new_plan=new_plan,
        plan_change_calls=plan_change_calls,
    )
    ctx = SimpleNamespace(team_id=1, set_warning=lambda *_a, **_k: None, incoming_data=None)

    result = module.apply_orders_route_plan_change(ctx, [1], 99)

    assert order.route_plan_id == 99
    assert order.route_group_id is None
    assert order.order_plan_objective == "international_shipping"
    assert plan_change_calls == [(10, 99)]
    assert result["updated"][0]["order"]["order_plan_objective"] == "international_shipping"


def test_moving_to_a_store_pickup_plan_adopts_its_objective(monkeypatch):
    order = _order()
    old_plan = _plan(10, "local_delivery")
    new_plan = _plan(77, "store_pickup")
    _install_common_stubs(
        monkeypatch,
        order=order,
        old_plan=old_plan,
        new_plan=new_plan,
        plan_change_calls=[],
    )
    ctx = SimpleNamespace(team_id=1, set_warning=lambda *_a, **_k: None, incoming_data=None)

    module.apply_orders_route_plan_change(ctx, [1], 77)

    assert order.order_plan_objective == "store_pickup"
    assert order.route_group_id is None


def test_route_group_id_is_rejected_for_a_non_local_destination(monkeypatch):
    order = _order()
    new_plan = _plan(99, "international_shipping")
    _install_common_stubs(
        monkeypatch,
        order=order,
        old_plan=_plan(10, "local_delivery"),
        new_plan=new_plan,
        plan_change_calls=[],
    )
    ctx = SimpleNamespace(team_id=1, set_warning=lambda *_a, **_k: None, incoming_data=None)

    with pytest.raises(ValidationFailed):
        module.apply_orders_route_plan_change(
            ctx, [1], 99, destination_route_group_id=5
        )


def test_local_destination_still_resolves_route_groups(monkeypatch):
    order = _order()
    new_plan = _plan(11, "local_delivery")
    _install_common_stubs(
        monkeypatch,
        order=order,
        old_plan=_plan(10, "local_delivery"),
        new_plan=new_plan,
        plan_change_calls=[],
    )
    monkeypatch.setattr(
        module,
        "_load_route_groups_for_plan",
        lambda *_a, **_k: [SimpleNamespace(id=42, zone_id=None)],
    )
    ctx = SimpleNamespace(team_id=1, set_warning=lambda *_a, **_k: None, incoming_data=None)

    module.apply_orders_route_plan_change(ctx, [1], 11)

    assert order.route_group_id == 42
    assert order.order_plan_objective == "local_delivery"
