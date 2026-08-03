from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.plan_changes import orchestrator as module
from Delivery_app_BK.services.commands.order.plan_changes.types import (
    PlanChangeApplyContext,
    PlanChangeResult,
)
from Delivery_app_BK.services.commands.order.plan_objectives import (
    orchestrator as objective_module,
)
from Delivery_app_BK.services.commands.order.plan_objectives.types import (
    PlanObjectiveCreateResult,
)


def _plan(plan_id: int, plan_type: str):
    return SimpleNamespace(id=plan_id, plan_type=plan_type)


def _recording_handlers(monkeypatch):
    """Replace every domain handler with a recorder of the sides it was handed."""
    calls: list[tuple[str, int | None, int | None]] = []

    def _make(plan_type: str):
        def _handler(ctx, order_instance, old_plan, new_plan, apply_context):
            calls.append(
                (
                    plan_type,
                    getattr(old_plan, "id", None),
                    getattr(new_plan, "id", None),
                )
            )
            return PlanChangeResult()

        return _handler

    monkeypatch.setattr(
        module,
        "PLAN_CHANGE_HANDLERS",
        {plan_type: _make(plan_type) for plan_type in module.PLAN_CHANGE_HANDLERS},
    )
    return calls


def test_move_within_local_delivery_stays_a_single_handler_call(monkeypatch):
    # Local delivery merges stop removal and creation into one incremental route
    # sync, so both sides must reach it together.
    calls = _recording_handlers(monkeypatch)

    module.apply_order_plan_change(
        SimpleNamespace(),
        SimpleNamespace(id=7),
        _plan(1, "local_delivery"),
        _plan(2, "local_delivery"),
        PlanChangeApplyContext(),
    )

    assert calls == [("local_delivery", 1, 2)]


def test_cross_domain_move_tears_down_the_old_domain_and_builds_the_new(monkeypatch):
    calls = _recording_handlers(monkeypatch)

    module.apply_order_plan_change(
        SimpleNamespace(),
        SimpleNamespace(id=7),
        _plan(1, "local_delivery"),
        _plan(2, "international_shipping"),
        PlanChangeApplyContext(),
    )

    # Local delivery sees only the source side, so it tears its stops down and
    # builds nothing. International shipping sees only the destination.
    assert calls == [
        ("local_delivery", 1, None),
        ("international_shipping", None, 2),
    ]


def test_move_into_local_delivery_from_another_domain(monkeypatch):
    calls = _recording_handlers(monkeypatch)

    module.apply_order_plan_change(
        SimpleNamespace(),
        SimpleNamespace(id=7),
        _plan(1, "store_pickup"),
        _plan(2, "local_delivery"),
        PlanChangeApplyContext(),
    )

    assert calls == [
        ("store_pickup", 1, None),
        ("local_delivery", None, 2),
    ]


def test_no_plans_on_either_side_is_a_no_op(monkeypatch):
    calls = _recording_handlers(monkeypatch)

    result = module.apply_order_plan_change(
        SimpleNamespace(),
        SimpleNamespace(id=7),
        None,
        None,
        PlanChangeApplyContext(),
    )

    assert calls == []
    assert result.instances == []
    assert result.serialize_bundle() == {}


def test_merged_result_collects_instances_and_bundles_from_both_domains(monkeypatch):
    def _local(ctx, order_instance, old_plan, new_plan, apply_context):
        return PlanChangeResult(
            instances=["stop"],
            bundle_serializer=lambda: {"order_stops": ["a"]},
        )

    def _international(ctx, order_instance, old_plan, new_plan, apply_context):
        return PlanChangeResult(
            instances=["shipment"],
            bundle_serializer=lambda: {"shipments": ["b"]},
        )

    monkeypatch.setattr(
        module,
        "PLAN_CHANGE_HANDLERS",
        {"local_delivery": _local, "international_shipping": _international},
    )

    result = module.apply_order_plan_change(
        SimpleNamespace(),
        SimpleNamespace(id=7),
        _plan(1, "local_delivery"),
        _plan(2, "international_shipping"),
        PlanChangeApplyContext(),
    )

    assert result.instances == ["stop", "shipment"]
    assert result.serialize_bundle() == {"order_stops": ["a"], "shipments": ["b"]}


# --- objective resolution -------------------------------------------------


def test_objective_is_taken_from_the_plan_not_the_order():
    # Previously an order could be created as international shipping while landing
    # on a local delivery plan, where the international handler is a no-op — so no
    # stop was built and the order never appeared on its route.
    order = SimpleNamespace(order_plan_objective=None)

    objective_module.apply_order_plan_objective(
        ctx=SimpleNamespace(),
        order_instance=order,
        route_plan=_plan(5, "store_pickup"),
    )

    assert order.order_plan_objective == "store_pickup"


def test_objective_contradicting_the_plan_is_rejected():
    order = SimpleNamespace(order_plan_objective="international_shipping")

    with pytest.raises(ValidationFailed):
        objective_module.apply_order_plan_objective(
            ctx=SimpleNamespace(),
            order_instance=order,
            route_plan=_plan(5, "local_delivery"),
        )


def test_legacy_objective_alias_still_matches_local_delivery(monkeypatch):
    # "route_operations" is legacy input for local delivery. It must normalize
    # rather than read as a contradiction against a local delivery plan.
    monkeypatch.setattr(
        objective_module,
        "PLAN_OBJECTIVE_HANDLERS",
        {"local_delivery": lambda *_args: PlanObjectiveCreateResult()},
    )
    order = SimpleNamespace(order_plan_objective="route_operations")

    objective_module.apply_order_plan_objective(
        ctx=SimpleNamespace(),
        order_instance=order,
        route_plan=_plan(5, "local_delivery"),
    )

    assert order.order_plan_objective == "local_delivery"


def test_objective_application_without_a_plan_is_a_no_op():
    order = SimpleNamespace(order_plan_objective="international_shipping")

    result = objective_module.apply_order_plan_objective(
        ctx=SimpleNamespace(),
        order_instance=order,
    )

    assert result.instances == []
    assert order.order_plan_objective == "international_shipping"
