from types import SimpleNamespace

import pytest

from Delivery_app_BK.ai.tools.plan_tools import optimize_plan_tool
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext


class _Outcome:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error


def test_optimize_plan_tool_translates_route_plan_id_to_route_group_id(monkeypatch):
    ctx = ServiceContext(incoming_data={}, identity={})
    route_plan = SimpleNamespace(id=55, route_groups=[SimpleNamespace(id=91)])

    monkeypatch.setattr("Delivery_app_BK.ai.tools.plan_tools.db.session.get", lambda model, plan_id: route_plan)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.plan_tools.optimize_route_plan",
        lambda context: _Outcome(data={"status": "optimized", "route_id": 7}),
    )

    result = optimize_plan_tool(ctx, route_plan_id=55)

    assert result["status"] == "optimized"
    assert ctx.incoming_data["route_plan_id"] == 55
    assert ctx.incoming_data["route_group_id"] == 91
    assert "route_group_id" in ctx.incoming_data
    assert all("route_group" in key or "route_plan" in key for key in ctx.incoming_data.keys())


def test_optimize_plan_tool_rejects_plan_without_route_group(monkeypatch):
    ctx = ServiceContext(incoming_data={}, identity={})
    route_plan = SimpleNamespace(id=55, route_groups=[])

    monkeypatch.setattr("Delivery_app_BK.ai.tools.plan_tools.db.session.get", lambda model, plan_id: route_plan)

    with pytest.raises(ValidationFailed):
        optimize_plan_tool(ctx, route_plan_id=55)
