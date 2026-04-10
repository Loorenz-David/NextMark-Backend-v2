import importlib
from types import SimpleNamespace

from Delivery_app_BK.services.context import ServiceContext


get_plan_module = importlib.import_module("Delivery_app_BK.services.queries.route_plan.get_plan")
plan_type_module = importlib.import_module(
    "Delivery_app_BK.services.queries.route_plan.plan_types.get_route_group"
)


def test_get_plan_returns_canonical_route_plan_key(monkeypatch):
    found_plan = SimpleNamespace(id=123)

    class _Query:
        def options(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def one_or_none(self):
            return found_plan

    monkeypatch.setattr(get_plan_module.db.session, "query", lambda *_args, **_kwargs: _Query())
    monkeypatch.setattr(
        get_plan_module,
        "serialize_plans",
        lambda instances, ctx, include_route_groups_summary=False: [{"id": 123, "label": "A"}],
    )

    result = get_plan_module.get_plan(123, ServiceContext(incoming_data={}, identity={}))

    assert "route_plan" in result
    assert "delivery_plan" not in result
    assert result["route_plan"]["id"] == 123


def test_get_route_group_plan_type_returns_canonical_route_group_type_key(monkeypatch):
    found_plan = SimpleNamespace(route_groups=[SimpleNamespace(id=77)])

    monkeypatch.setattr(plan_type_module, "get_instance", lambda **_kwargs: found_plan)
    monkeypatch.setattr(plan_type_module, "serialize_route_group", lambda instance, ctx: {"id": 77})

    result = plan_type_module.get_route_group_plan_type(
        123,
        ServiceContext(incoming_data={}, identity={}),
    )

    assert "route_group_type" in result
    assert "delivery_plan_type" not in result
    assert result["route_group_type"]["id"] == 77
