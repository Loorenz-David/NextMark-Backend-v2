import importlib
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import NotFound, ValidationFailed


module = importlib.import_module("Delivery_app_BK.services.queries.order.get_order_route_context")


class _DummyQuery:
    def __init__(self, results):
        self._results = results

    def join(self, *_args, **_kwargs):
        return self

    def options(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._results)


def _ctx():
    return SimpleNamespace(team_id=1, check_team_id=True)


def _route_solution(route_plan_id=42, route_group_id=7):
    return SimpleNamespace(
        id=731,
        route_group_id=route_group_id,
        route_group=SimpleNamespace(route_plan_id=route_plan_id, route_plan=SimpleNamespace(id=route_plan_id, label="Plan 42")),
    )


def _stop(stop_id=99, route_solution_id=731, order_id=4371):
    solution = _route_solution()
    solution.id = route_solution_id
    return SimpleNamespace(
        id=stop_id,
        route_solution_id=route_solution_id,
        route_solution=solution,
        order_id=order_id,
    )


def test_get_order_route_context_returns_solution_and_stop(monkeypatch):
    order = SimpleNamespace(id=4371)
    stop = _stop()

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: order)
    monkeypatch.setattr(module.db.session, "query", lambda _model: _DummyQuery([stop]))
    monkeypatch.setattr(module, "serialize_route_solution", lambda solution: {"id": solution.id})
    monkeypatch.setattr(
        module,
        "serialize_route_solution_stops",
        lambda stops, _ctx: {
            "byClientId": {str(stops[0].id): {"id": stops[0].id}},
            "allIds": [str(stops[0].id)],
        },
    )

    result = module.get_order_route_context(4371, _ctx())

    assert result == {
        "order_id": 4371,
        "route_solution": {"id": 731},
        "route_solution_stop": {"id": 99},
        "route_plan_id": 42,
        "route_group_id": 7,
    }


def test_unwrap_single_serialized_stop_accepts_list_and_client_id_map():
    assert module._unwrap_single_serialized_stop([{"id": 1}]) == {"id": 1}
    assert module._unwrap_single_serialized_stop(
        {"byClientId": {"1": {"id": 1}}, "allIds": ["1"]}
    ) == {"id": 1}


def test_get_order_route_context_raises_not_found_when_order_has_no_selected_route(monkeypatch):
    order = SimpleNamespace(id=4371)

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: order)
    monkeypatch.setattr(module.db.session, "query", lambda _model: _DummyQuery([]))

    with pytest.raises(NotFound, match="No selected route solution found"):
        module.get_order_route_context(4371, _ctx())


def test_get_order_route_context_rejects_multiple_selected_stops(monkeypatch):
    order = SimpleNamespace(id=4371)
    stop_a = _stop(stop_id=1)
    stop_b = _stop(stop_id=2)

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: order)
    monkeypatch.setattr(module.db.session, "query", lambda _model: _DummyQuery([stop_a, stop_b]))

    with pytest.raises(ValidationFailed, match="Expected exactly one selected route stop"):
        module.get_order_route_context(4371, _ctx())
