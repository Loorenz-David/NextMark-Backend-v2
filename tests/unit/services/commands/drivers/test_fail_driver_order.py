import importlib
from types import SimpleNamespace

module = importlib.import_module("Delivery_app_BK.services.commands.drivers.fail_driver_order")


def test_fail_driver_order_transitions_state_with_failure_note(monkeypatch):
    order = SimpleNamespace(id=18, order_state_id=4, client_id="ord_18")
    captured = {}

    monkeypatch.setattr(
        module,
        "resolve_driver_action_order_stop",
        lambda ctx, order_id: (order, SimpleNamespace(id=91)),
    )

    def _fake_update_orders_state(*, ctx, orders, state_id):
        captured["ctx"] = ctx
        captured["orders"] = orders
        captured["state_id"] = state_id
        order.order_state_id = state_id
        order.order_notes = [
            {
                "type": "FAILURE",
                "content": ctx.incoming_data["order_notes"]["content"],
            }
        ]
        return [order]

    monkeypatch.setattr(module, "update_orders_state", _fake_update_orders_state)
    monkeypatch.setattr(
        module,
        "serialize_driver_order_command_delta",
        lambda instances, ctx: [{"id": instances[0].id, "order_state_id": instances[0].order_state_id}],
    )

    result = module.fail_driver_order(
        SimpleNamespace(
            incoming_data={"description": "Customer not at home"},
            identity={"team_id": 7},
            check_team_id=True,
            inject_team_id=True,
            skip_id_instance_injection=False,
        ),
        18,
    )

    assert captured["orders"] == [order]
    assert captured["state_id"] == 7
    assert captured["ctx"].incoming_data == {
        "order_notes": {
            "type": "FAILURE",
            "content": "Customer not at home",
        }
    }
    assert result == {"orders": [{"id": 18, "order_state_id": 7}]}
