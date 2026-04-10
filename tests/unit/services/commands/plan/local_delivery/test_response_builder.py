from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.local_delivery import response_builder as module


def test_response_builder_returns_route_solution_without_stops_when_only_route_changes(
    monkeypatch,
):
    route_solution = SimpleNamespace(stops=[SimpleNamespace(id=1)])
    ctx = SimpleNamespace()

    monkeypatch.setattr(
        module,
        "serialize_route_solutions",
        lambda instances, _ctx: [{"id": 10}] if instances else [],
    )
    monkeypatch.setattr(
        module,
        "serialize_route_solution_stops",
        lambda instances, _ctx: [{"id": stop.id} for stop in instances],
    )

    outcome = module.build_local_delivery_settings_response(
        ctx=ctx,
        route_solution=route_solution,
        stops_changed=False,
        route_solution_changed=True,
    )

    assert outcome == {"route_solution": [{"id": 10}]}


def test_response_builder_returns_empty_when_nothing_changed(monkeypatch):
    route_solution = SimpleNamespace(stops=[SimpleNamespace(id=1)])
    ctx = SimpleNamespace()

    monkeypatch.setattr(module, "serialize_route_solutions", lambda *_args: [])
    monkeypatch.setattr(module, "serialize_route_solution_stops", lambda *_args: [])

    outcome = module.build_local_delivery_settings_response(
        ctx=ctx,
        route_solution=route_solution,
        stops_changed=False,
        route_solution_changed=False,
    )

    assert outcome == {}

