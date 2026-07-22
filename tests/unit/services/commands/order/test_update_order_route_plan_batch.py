from types import SimpleNamespace

from Delivery_app_BK.services.commands.order import update_order_route_plan_batch as module


def test_batch_route_plan_update_delegates_resolved_orders_to_shared_move(monkeypatch):
    resolved = SimpleNamespace(
        signature="selection-signature",
        resolved_count=2,
        sample_ids=[11, 12],
        order_ids=[11, 12],
    )
    captured = {}

    monkeypatch.setattr(
        module,
        "parse_update_orders_route_plan_batch_payload",
        lambda incoming_data: SimpleNamespace(),
    )
    monkeypatch.setattr(
        module,
        "_run_selection_resolution_transaction",
        lambda resolver: resolved,
    )
    monkeypatch.setattr(
        module,
        "update_orders_route_plan",
        lambda ctx, order_ids, plan_id, destination_route_group_id=None: (
            captured.update(
                order_ids=order_ids,
                plan_id=plan_id,
                destination_route_group_id=destination_route_group_id,
            )
            or {"updated": [{"order": {"id": order_id}} for order_id in order_ids]}
        ),
    )

    result = module.update_orders_route_plan_batch(
        ctx=SimpleNamespace(incoming_data={}),
        plan_id=7,
        destination_route_group_id=3,
    )

    assert captured == {
        "order_ids": [11, 12],
        "plan_id": 7,
        "destination_route_group_id": 3,
    }
    assert result == {
        "signature": "selection-signature",
        "resolved_count": 2,
        "updated_count": 2,
        "updated_bundles": [
            {"order": {"id": 11}},
            {"order": {"id": 12}},
        ],
    }
