from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import (
    derive_plan_state_from_groups,
    maybe_sync_plan_state_from_groups,
)
from Delivery_app_BK.services.domain.state_transitions.route_group_state_engine import (
    derive_route_group_state,
    maybe_sync_route_group_state,
)


def _order(state_id: int):
    return SimpleNamespace(order_state_id=state_id)


def _route_group(state_id: int | None = None, orders=None, deleted_at=None):
    return SimpleNamespace(state_id=state_id, orders=list(orders or []), deleted_at=deleted_at)


def _plan(state_id: int | None = None, route_groups=None):
    return SimpleNamespace(id=1, state_id=state_id, route_groups=list(route_groups or []))


def test_derive_route_group_state_excludes_cancelled_orders():
    group = _route_group(
        orders=[
            _order(OrderStateId.CANCELLED),
            _order(OrderStateId.PROCESSING),
            _order(OrderStateId.CANCELLED),
        ]
    )

    assert derive_route_group_state(group) == PlanStateId.PROCESSING


def test_derive_route_group_state_returns_open_for_empty_active_orders():
    group = _route_group(orders=[_order(OrderStateId.CANCELLED)])

    assert derive_route_group_state(group) == PlanStateId.OPEN


def test_maybe_sync_route_group_state_updates_when_needed():
    group = _route_group(state_id=PlanStateId.OPEN, orders=[_order(OrderStateId.READY)])

    changed = maybe_sync_route_group_state(group)

    assert changed is True
    assert group.state_id == PlanStateId.READY


def test_derive_plan_state_from_groups_strict_all_match():
    plan = _plan(
        route_groups=[
            _route_group(state_id=PlanStateId.READY),
            _route_group(state_id=PlanStateId.READY),
        ]
    )

    assert derive_plan_state_from_groups(plan) == PlanStateId.READY


def test_derive_plan_state_from_groups_mixed_is_open():
    plan = _plan(
        route_groups=[
            _route_group(state_id=PlanStateId.READY),
            _route_group(state_id=PlanStateId.PROCESSING),
        ]
    )

    assert derive_plan_state_from_groups(plan) == PlanStateId.OPEN


def test_maybe_sync_plan_state_from_groups_applies_derived_state():
    plan = _plan(
        state_id=PlanStateId.OPEN,
        route_groups=[
            _route_group(state_id=PlanStateId.COMPLETED),
            _route_group(state_id=PlanStateId.COMPLETED),
        ],
    )

    changed = maybe_sync_plan_state_from_groups(plan)

    assert changed is True
    assert plan.state_id == PlanStateId.COMPLETED
