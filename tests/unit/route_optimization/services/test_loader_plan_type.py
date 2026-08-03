from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.services import loader as module


class _FakeQuery:
    """Records the criteria the loader filters orders by."""

    def __init__(self, rows, recorded_criteria):
        self._rows = rows
        self._recorded = recorded_criteria

    def options(self, *_args, **_kwargs):
        return self

    def filter(self, *criteria):
        self._recorded.extend(str(criterion) for criterion in criteria)
        return self

    def all(self):
        return self._rows


def _install(monkeypatch, *, plan_type, rows=None, recorded=None):
    route_plan = SimpleNamespace(id=3, plan_type=plan_type, date_strategy="single")
    route_solution = SimpleNamespace(is_selected=True, route_end_strategy=None, vehicle_id=None)
    route_group = SimpleNamespace(
        id=8, route_plan=route_plan, route_solutions=[route_solution]
    )

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: route_group)
    monkeypatch.setattr(module, "is_route_solution_end_date_valid", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "_select_route_solution", lambda *_a, **_k: route_solution)
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(
            session=SimpleNamespace(
                query=lambda *_a, **_k: _FakeQuery(
                    rows if rows is not None else [SimpleNamespace(id=1)],
                    recorded if recorded is not None else [],
                ),
                get=lambda *_a, **_k: None,
            )
        ),
    )
    return route_plan


def _ctx():
    return SimpleNamespace(
        incoming_data={"route_group_id": 8},
        identity={"team_id": 1},
        team_id=1,
    )


@pytest.mark.parametrize("plan_type", ["international_shipping", "store_pickup"])
def test_optimizing_a_non_local_plan_is_refused(monkeypatch, plan_type):
    # Fails with a plan-type message rather than the misleading "has no orders
    # to optimize" it would otherwise reach.
    _install(monkeypatch, plan_type=plan_type)

    with pytest.raises(ValidationFailed) as exc:
        module.load_optimization_context(_ctx())

    assert "local delivery" in str(exc.value)


def test_orders_are_restricted_to_the_local_delivery_objective(monkeypatch):
    # Shipments are built from every order on the plan, stop or no stop, so a
    # foreign order must never enter the context in the first place.
    recorded: list[str] = []
    _install(monkeypatch, plan_type="local_delivery", recorded=recorded)

    module.load_optimization_context(_ctx())

    assert any("order_plan_objective" in criterion for criterion in recorded)
    assert any("route_plan_id" in criterion for criterion in recorded)


def test_local_delivery_plan_still_loads_its_orders(monkeypatch):
    orders = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    _install(monkeypatch, plan_type="local_delivery", rows=orders)

    context = module.load_optimization_context(_ctx())

    assert context.orders == orders
    assert context.route_plan.plan_type == "local_delivery"
