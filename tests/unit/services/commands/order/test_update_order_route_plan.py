import pytest
from types import SimpleNamespace

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order import update_order_route_plan as module


def test_normalize_order_ids_accepts_single_int():
    assert module._normalize_order_ids(5) == [5]


def test_normalize_order_ids_dedupes_list():
    assert module._normalize_order_ids([1, 1, 2]) == [1, 2]


def test_normalize_order_ids_rejects_string_ids():
    with pytest.raises(ValidationFailed):
        module._normalize_order_ids(["client-1"])  # type: ignore[list-item]


def test_apply_move_state_heritage_recomputes_group_counts(monkeypatch):
    order = SimpleNamespace(id=1, order_state_id=2)
    route_group = SimpleNamespace(id=20)
    new_plan = SimpleNamespace(id=15)

    calls = {
        "plan_recompute": 0,
        "group_recompute": 0,
        "plan_auto": 0,
        "group_sync": 0,
        "plan_sync": 0,
    }

    monkeypatch.setattr(
        module,
        "compute_destination_move_result",
        lambda *_args, **_kwargs: SimpleNamespace(
            new_order_state_id=None,
            new_plan_state_id=None,
            should_create_case=False,
            case_predefined_text=None,
        ),
    )
    monkeypatch.setattr(
        module,
        "recompute_plan_order_counts",
        lambda _plan: calls.__setitem__("plan_recompute", calls["plan_recompute"] + 1),
    )
    monkeypatch.setattr(
        module,
        "recompute_route_group_order_counts",
        lambda _group: calls.__setitem__("group_recompute", calls["group_recompute"] + 1),
    )
    monkeypatch.setattr(
        module,
        "maybe_auto_complete_plan",
        lambda _plan: calls.__setitem__("plan_auto", calls["plan_auto"] + 1),
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

    module._apply_move_state_heritage(
        ctx=SimpleNamespace(identity=None, incoming_data={}),
        changed_orders=[order],
        new_plan=new_plan,
        plans_to_recompute={new_plan.id: new_plan},
        affected_route_groups=[route_group],
        case_message=None,
    )

    assert calls == {
        "plan_recompute": 1,
        "group_recompute": 1,
        "plan_auto": 1,
        "group_sync": 1,
        "plan_sync": 1,
    }


def test_build_state_changes_bundle_serializes_route_groups_and_plans():
    route_groups = [
        SimpleNamespace(
            id=10,
            state_id=4,
            total_orders=3,
            order_state_counts={"Ready": 3},
            route_plan_id=1,
            zone_id=7,
        ),
        SimpleNamespace(
            id=11,
            state_id=2,
            total_orders=0,
            order_state_counts=None,
            route_plan_id=1,
            zone_id=8,
        ),
    ]
    route_plans = [
        SimpleNamespace(id=1, state_id=4, total_orders=3),
        SimpleNamespace(id=2, state_id=2, total_orders=0),
    ]

    result = module._build_state_changes_bundle(
        route_groups=route_groups,
        route_plans=route_plans,
    )

    assert result == {
        "route_groups": [
            {
                "id": 10,
                "state_id": 4,
                "total_orders": 3,
                "order_state_counts": {"Ready": 3},
                "route_plan_id": 1,
                "zone_id": 7,
            },
            {
                "id": 11,
                "state_id": 2,
                "total_orders": 0,
                "order_state_counts": None,
                "route_plan_id": 1,
                "zone_id": 8,
            },
        ],
        "route_plans": [
            {"id": 1, "state_id": 4, "total_orders": 3},
            {"id": 2, "state_id": 2, "total_orders": 0},
        ],
    }


def test_apply_orders_route_plan_unassign_preserves_order_plan_objective(monkeypatch):
    order = SimpleNamespace(
        id=1,
        route_plan_id=10,
        route_group_id=20,
        order_plan_objective="local_delivery",
    )
    plan = SimpleNamespace(
        id=10,
        route_groups=[],
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        total_orders=0,
    )
    ctx = SimpleNamespace(set_warning=lambda *_args, **_kwargs: None)

    monkeypatch.setattr(module, "_resolve_orders_for_update", lambda *_args, **_kwargs: {1: order})
    monkeypatch.setattr(module, "_get_order_route_plan_id", lambda instance: instance.route_plan_id)
    monkeypatch.setattr(module, "_get_order_route_group_id", lambda instance: instance.route_group_id)
    monkeypatch.setattr(module, "_load_route_plans_by_id", lambda *_args, **_kwargs: {10: plan})
    monkeypatch.setattr(
        module,
        "build_plan_change_apply_context",
        lambda **_kwargs: SimpleNamespace(source_route_group_id_by_order_id={}),
    )
    monkeypatch.setattr(
        module,
        "_prepare_old_local_delivery_batch_changes",
        lambda **_kwargs: {
            "order_ids": set(),
            "instances": [],
            "post_flush_actions": [],
            "updated_stops": [],
            "synced_stops": [],
            "updated_route_solutions": [],
            "synced_route_solutions": [],
        },
    )
    monkeypatch.setattr(module, "_set_order_route_plan_id", lambda instance, value: setattr(instance, "route_plan_id", value))
    monkeypatch.setattr(module, "_set_order_route_group_id", lambda instance, value: setattr(instance, "route_group_id", value))
    monkeypatch.setattr(
        module,
        "apply_order_plan_change",
        lambda **_kwargs: SimpleNamespace(
            instances=[],
            post_flush_actions=[],
            serialize_bundle=lambda: {},
        ),
    )
    monkeypatch.setattr(module, "build_route_plan_changed_event", lambda *_args, **_kwargs: {"event_name": "changed"})
    monkeypatch.setattr(module, "_sanitize_instances_for_session", lambda instances: instances)
    monkeypatch.setattr(module, "touch_route_freshness", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "recompute_plan_totals", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "recompute_route_group_totals", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "recompute_plan_order_counts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "maybe_auto_complete_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "recompute_route_group_order_counts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "maybe_sync_route_group_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "maybe_sync_plan_state_from_groups", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_serialize_old_local_delivery_batch_bundle",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        module,
        "_build_state_changes_bundle",
        lambda **_kwargs: {"route_groups": [], "route_plans": []},
    )
    monkeypatch.setattr(
        module,
        "serialize_created_order",
        lambda instance: {
            "id": instance.id,
            "route_plan_id": instance.route_plan_id,
            "route_group_id": instance.route_group_id,
            "order_plan_objective": instance.order_plan_objective,
        },
    )
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(session=SimpleNamespace(add_all=lambda *_args, **_kwargs: None, flush=lambda: None)),
    )

    result = module.apply_orders_route_plan_unassign(ctx, [1])

    assert order.route_plan_id is None
    assert order.route_group_id is None
    assert order.order_plan_objective == "local_delivery"
    assert result["updated"][0]["order"]["order_plan_objective"] == "local_delivery"
