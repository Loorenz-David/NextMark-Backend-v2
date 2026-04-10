import importlib
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
module = importlib.import_module("Delivery_app_BK.services.overviews.local_delivery_overview")


def _route_solution(solution_id: int, *, is_selected: bool, stops=None):
    return SimpleNamespace(
        id=solution_id,
        is_selected=is_selected,
        client_id=f"route_solution:{solution_id}",
        stops=stops or [],
    )


def _route_group(group_id: int, name: str, route_solutions=None):
    return SimpleNamespace(
        id=group_id,
        name=name,
        route_solutions=route_solutions or [],
    )


def _plan(route_groups):
    return SimpleNamespace(
        id=100,
        plan_type="local_delivery",
        route_groups=route_groups,
        orders=[SimpleNamespace(id=501), SimpleNamespace(id=502)],
    )


def test_local_delivery_overview_selects_requested_route_group(monkeypatch):
    group_a = _route_group(
        10,
        "Zone A",
        route_solutions=[
            _route_solution(101, is_selected=True, stops=[SimpleNamespace(id=301)])
        ],
    )
    group_b = _route_group(
        20,
        "Zone B",
        route_solutions=[
            _route_solution(201, is_selected=True, stops=[SimpleNamespace(id=401)])
        ],
    )
    plan = _plan([group_a, group_b])

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: plan)
    monkeypatch.setattr(module, "serialize_orders", lambda instances, ctx: [order.id for order in instances])
    monkeypatch.setattr(
        module,
        "serialize_route_groups",
        lambda instances, ctx: [route_group.id for route_group in instances],
    )
    monkeypatch.setattr(
        module,
        "serialize_route_solutions_mixed",
        lambda selected, others, ctx: {
            "selected": selected.id,
            "others": [route_solution.id for route_solution in others],
        },
    )
    monkeypatch.setattr(
        module,
        "serialize_route_solution_stops",
        lambda instances, ctx: [stop.id for stop in instances],
    )

    ctx = ServiceContext(query_params={"route_group_id": "20"}, identity={})
    result = module.local_delivery_overview(ctx, 100)

    assert result["route_group"] == [10, 20]
    assert result["route_solution"]["selected"] == 201
    assert result["route_solution_stop"] == [401]


def test_local_delivery_overview_falls_back_to_first_route_group(monkeypatch):
    group_a = _route_group(
        10,
        "Zone A",
        route_solutions=[
            _route_solution(101, is_selected=False, stops=[SimpleNamespace(id=301)]),
            _route_solution(102, is_selected=False, stops=[SimpleNamespace(id=302)]),
        ],
    )
    group_b = _route_group(
        20,
        "Zone B",
        route_solutions=[
            _route_solution(201, is_selected=True, stops=[SimpleNamespace(id=401)])
        ],
    )
    plan = _plan([group_b, group_a])

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: plan)
    monkeypatch.setattr(module, "serialize_orders", lambda instances, ctx: [order.id for order in instances])
    monkeypatch.setattr(
        module,
        "serialize_route_groups",
        lambda instances, ctx: [route_group.id for route_group in instances],
    )
    monkeypatch.setattr(
        module,
        "serialize_route_solutions_mixed",
        lambda selected, others, ctx: {
            "selected": selected.id,
            "others": [route_solution.id for route_solution in others],
        },
    )
    monkeypatch.setattr(
        module,
        "serialize_route_solution_stops",
        lambda instances, ctx: [stop.id for stop in instances],
    )

    ctx = ServiceContext(query_params={}, identity={})
    result = module.local_delivery_overview(ctx, 100)

    # Sorted by route-group name, so Zone A is selected first.
    assert result["route_group"] == [10, 20]
    assert result["route_solution"]["selected"] == 101
    assert result["route_solution_stop"] == [301]
    assert ctx.warnings


def test_local_delivery_overview_rejects_foreign_route_group_id(monkeypatch):
    plan = _plan([
        _route_group(
            10,
            "Zone A",
            route_solutions=[
                _route_solution(101, is_selected=True, stops=[SimpleNamespace(id=301)])
            ],
        )
    ])

    monkeypatch.setattr(module, "get_instance", lambda **_kwargs: plan)

    ctx = ServiceContext(query_params={"route_group_id": "999"}, identity={})
    with pytest.raises(ValidationFailed, match="does not belong"):
        module.local_delivery_overview(ctx, 100)


def test_parse_route_group_id_rejects_non_integer():
    ctx = ServiceContext(query_params={"route_group_id": "abc"}, identity={})
    with pytest.raises(ValidationFailed, match="must be an integer"):
        module._parse_route_group_id(ctx)
