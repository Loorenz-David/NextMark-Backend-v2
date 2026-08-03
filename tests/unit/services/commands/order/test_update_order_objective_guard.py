from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order import update_order as module
from Delivery_app_BK.services.commands.order.update_extensions import (
    orchestrator as update_extensions_orchestrator,
)
from Delivery_app_BK.services.commands.order.update_extensions.types import (
    OrderUpdateDelta,
    OrderUpdateChangeFlags,
)


def _order(*, route_plan_id, objective="local_delivery"):
    return SimpleNamespace(
        id=1,
        route_plan_id=route_plan_id,
        order_plan_objective=objective,
    )


def test_objective_change_is_rejected_while_the_order_sits_on_a_plan():
    # Changing it here would desync the order from its plan and strand the stops
    # the local delivery domain built for it.
    order = _order(route_plan_id=7)

    with pytest.raises(ValidationFailed):
        module._reject_objective_change_on_assigned_order(
            order, {"order_plan_objective": "international_shipping"}
        )


def test_objective_change_is_allowed_when_the_order_is_unassigned():
    order = _order(route_plan_id=None)

    module._reject_objective_change_on_assigned_order(
        order, {"order_plan_objective": "international_shipping"}
    )


def test_repeating_the_current_objective_is_not_a_change():
    # Clients echo the whole order back on PATCH; that must not read as a move.
    order = _order(route_plan_id=7, objective="local_delivery")

    module._reject_objective_change_on_assigned_order(
        order, {"order_plan_objective": "local_delivery"}
    )


def test_legacy_alias_counts_as_the_current_objective():
    order = _order(route_plan_id=7, objective="local_delivery")

    module._reject_objective_change_on_assigned_order(
        order, {"order_plan_objective": "route_operations"}
    )


def test_payload_without_the_field_is_untouched():
    order = _order(route_plan_id=7)

    module._reject_objective_change_on_assigned_order(order, {"client_email": "a@b.c"})


# --- freshness + extension dispatch key off the plan, not the order ----------


def _delta(plan, *, objective, changed_sections=("address",)):
    return OrderUpdateDelta(
        order_instance=SimpleNamespace(id=1, order_plan_objective=objective),
        old_values={},
        new_values={},
        flags=OrderUpdateChangeFlags(),
        changed_sections=changed_sections,
        delivery_plan=plan,
    )


def test_extension_dispatch_follows_the_plan_type_not_the_order_objective():
    # A drifted order must not route its update through another domain's handler.
    delta = _delta(
        SimpleNamespace(id=3, plan_type="store_pickup"),
        objective="local_delivery",
    )

    assert update_extensions_orchestrator._resolve_plan_type(delta) == "store_pickup"


def test_extension_dispatch_is_skipped_for_an_unassigned_order():
    delta = _delta(None, objective="local_delivery")

    assert update_extensions_orchestrator._resolve_plan_type(delta) is None
