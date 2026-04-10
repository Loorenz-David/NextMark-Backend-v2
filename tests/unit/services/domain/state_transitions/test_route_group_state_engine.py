from types import SimpleNamespace

from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.domain.state_transitions import route_group_state_engine as module


def test_derive_route_group_state_uses_order_state_counts_ready():
    route_group = SimpleNamespace(
        order_state_counts={"Ready": 3},
        total_orders=3,
        orders=[SimpleNamespace(order_state_id=5)],
    )

    result = module.derive_route_group_state(route_group)

    assert result == PlanStateId.READY


def test_derive_route_group_state_uses_order_state_counts_open_when_empty_after_move():
    route_group = SimpleNamespace(
        order_state_counts={"Cancelled": 1},
        total_orders=1,
        orders=[SimpleNamespace(order_state_id=4)],
    )

    result = module.derive_route_group_state(route_group)

    assert result == PlanStateId.OPEN


def test_derive_route_group_state_falls_back_to_orders_when_counts_missing():
    route_group = SimpleNamespace(
        order_state_counts=None,
        total_orders=None,
        orders=[SimpleNamespace(order_state_id=4), SimpleNamespace(order_state_id=4)],
    )

    result = module.derive_route_group_state(route_group)

    assert result == PlanStateId.READY
