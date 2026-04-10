from types import SimpleNamespace

from Delivery_app_BK.services.queries.order import serialize_state_update as module


def test_build_order_state_update_payload_includes_orders_groups_and_plans(monkeypatch):
    changed_orders = [
        SimpleNamespace(
            id=11,
            client_id="order_11",
            order_state_id=4,
            route_group_id=15,
            route_plan_id=12,
        )
    ]

    monkeypatch.setattr(
        module,
        "_load_route_groups_by_ids",
        lambda ids: [
            SimpleNamespace(
                id=15,
                client_id="route_group_15",
                route_plan_id=12,
                state_id=2,
                total_orders=4,
                order_state_counts={"Ready": 3, "Preparing": 1},
            )
        ]
        if ids == {15}
        else [],
    )
    monkeypatch.setattr(
        module,
        "_load_route_plans_by_ids",
        lambda ids: [
            SimpleNamespace(
                id=12,
                client_id="route_plan_12",
                state_id=2,
                total_orders=4,
            )
        ]
        if ids == {12}
        else [],
    )

    payload = module.build_order_state_update_payload(changed_orders)

    assert payload["orders"] == [
        {
            "id": 11,
            "client_id": "order_11",
            "order_state_id": 4,
            "route_group_id": 15,
            "route_plan_id": 12,
        }
    ]
    assert payload["route_groups"] == [
        {
            "id": 15,
            "client_id": "route_group_15",
            "route_plan_id": 12,
            "state_id": 2,
            "total_orders": 4,
            "order_state_counts": {"Ready": 3, "Preparing": 1},
        }
    ]
    assert payload["route_plans"] == [
        {
            "id": 12,
            "client_id": "route_plan_12",
            "state_id": 2,
            "total_orders": 4,
        }
    ]


def test_build_order_state_update_payload_resolves_ids_from_relationships(monkeypatch):
    route_group = SimpleNamespace(id=21)
    route_plan = SimpleNamespace(id=31)
    changed_orders = [
        SimpleNamespace(
            id=44,
            client_id="order_44",
            order_state_id=3,
            route_group_id=None,
            route_plan_id=None,
            route_group=route_group,
            route_plan=route_plan,
            delivery_plan=None,
        )
    ]

    monkeypatch.setattr(module, "_load_route_groups_by_ids", lambda ids: [] if ids != {21} else [])
    monkeypatch.setattr(module, "_load_route_plans_by_ids", lambda ids: [] if ids != {31} else [])

    payload = module.build_order_state_update_payload(changed_orders)

    assert payload["orders"][0]["route_group_id"] == 21
    assert payload["orders"][0]["route_plan_id"] == 31
    assert payload["route_groups"] == []
    assert payload["route_plans"] == []
