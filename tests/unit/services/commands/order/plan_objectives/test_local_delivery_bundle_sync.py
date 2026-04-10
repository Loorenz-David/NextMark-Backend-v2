from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_OPTIMIZE,
)
from Delivery_app_BK.services.commands.order.plan_objectives import local_delivery as module
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    incremental_sync as sync_module,
)


class DummyCtx:
    def __init__(self) -> None:
        self.team_id = 1
        self.time_zone = "UTC"
        self.warnings: list[str] = []

    def set_warning(self, message: str) -> None:
        self.warnings.append(message)


def _make_stop(
    *,
    stop_id: int,
    client_id: str,
    route_solution_id: int,
    stop_order: int,
    order_id: int | None,
    to_next_polyline: str | None,
):
    return SimpleNamespace(
        id=stop_id,
        client_id=client_id,
        route_solution_id=route_solution_id,
        order_id=order_id,
        service_duration="0",
        in_range=True,
        stop_order=stop_order,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        eta_status="valid",
        expected_arrival_time=datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        actual_arrival_time=None,
        to_next_polyline=to_next_polyline,
    )


def _setup_fixture(is_optimized: str = IS_OPTIMIZED_OPTIMIZE):
    order_instance = SimpleNamespace(id=501)
    predecessor = _make_stop(
        stop_id=1,
        client_id="rs_prev",
        route_solution_id=10,
        stop_order=1,
        order_id=500,
        to_next_polyline="old-prev-segment",
    )
    created = _make_stop(
        stop_id=2,
        client_id="rs_new",
        route_solution_id=10,
        stop_order=2,
        order_id=None,
        to_next_polyline="old-new-segment",
    )
    route_solution = SimpleNamespace(
        id=10,
        is_optimized=is_optimized,
        stops=[predecessor, created],
        start_leg_polyline="start-seg",
        end_leg_polyline="end-seg",
    )
    delivery_plan = SimpleNamespace(
        id=77,
        orders=[SimpleNamespace(id=500), SimpleNamespace(id=501)],
    )
    local_delivery_plan = SimpleNamespace(route_solutions=[route_solution])
    return order_instance, predecessor, created, route_solution, delivery_plan, local_delivery_plan


def test_bundle_includes_created_and_synced_stops(monkeypatch):
    ctx = DummyCtx()
    order_instance, predecessor, created, route_solution, delivery_plan, local_delivery_plan = _setup_fixture()

    monkeypatch.setattr(
        module,
        "serialize_route_solution",
        lambda route_solution: {"id": route_solution.id, "client_id": "route_10"},
    )
    monkeypatch.setattr(module, "_get_route_group", lambda *_, **__: local_delivery_plan)

    def _build_stops(*args, **kwargs):
        return [created], [(created, order_instance)], [route_solution]

    monkeypatch.setattr(module, "build_route_solution_stops", _build_stops)

    def _refresh(**kwargs):
        predecessor.to_next_polyline = "new-prev-segment"
        return [predecessor, created]

    monkeypatch.setattr(sync_module, "refresh_route_solution_incremental", _refresh)

    result = module.apply_local_delivery_objective(
        ctx=ctx,
        order_instance=order_instance,
        route_plan=delivery_plan,
        plan_objective="local_delivery",
    )

    for action in result.post_flush_actions:
        action()

    bundle = result.serialize_bundle()
    assert "order_stops" in bundle
    assert "route_solution" in bundle
    assert bundle["route_solution"][0]["id"] == 10
    serialized = bundle["order_stops"]

    assert len(serialized) == 2
    assert {entry["id"] for entry in serialized} == {1, 2}
    prev = next(entry for entry in serialized if entry["id"] == 1)
    assert prev["to_next_polyline"] == "new-prev-segment"


def test_bundle_includes_stale_changed_stops_on_soft_fail(monkeypatch):
    ctx = DummyCtx()
    order_instance, predecessor, created, route_solution, delivery_plan, local_delivery_plan = _setup_fixture()

    monkeypatch.setattr(
        module,
        "serialize_route_solution",
        lambda route_solution: {"id": route_solution.id, "client_id": "route_10"},
    )
    monkeypatch.setattr(module, "_get_route_group", lambda *_, **__: local_delivery_plan)
    monkeypatch.setattr(
        module,
        "build_route_solution_stops",
        lambda *args, **kwargs: ([created], [(created, order_instance)], [route_solution]),
    )

    def _refresh(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(sync_module, "refresh_route_solution_incremental", _refresh)

    result = module.apply_local_delivery_objective(
        ctx=ctx,
        order_instance=order_instance,
        route_plan=delivery_plan,
        plan_objective="local_delivery",
    )

    for action in result.post_flush_actions:
        action()

    bundle = result.serialize_bundle()
    serialized = bundle["order_stops"]

    assert len(serialized) == 2
    prev = next(entry for entry in serialized if entry["id"] == 1)
    new = next(entry for entry in serialized if entry["id"] == 2)
    assert prev["to_next_polyline"] is None
    assert new["to_next_polyline"] is None
    assert new["eta_status"] == "stale"
    assert ctx.warnings


def test_bundle_dedupes_stops_when_created_is_also_synced(monkeypatch):
    ctx = DummyCtx()
    order_instance, predecessor, created, route_solution, delivery_plan, local_delivery_plan = _setup_fixture()

    monkeypatch.setattr(
        module,
        "serialize_route_solution",
        lambda route_solution: {"id": route_solution.id, "client_id": "route_10"},
    )
    monkeypatch.setattr(module, "_get_route_group", lambda *_, **__: local_delivery_plan)
    monkeypatch.setattr(
        module,
        "build_route_solution_stops",
        lambda *args, **kwargs: ([created], [(created, order_instance)], [route_solution]),
    )
    monkeypatch.setattr(
        sync_module,
        "refresh_route_solution_incremental",
        lambda **kwargs: [created, predecessor, created],
    )

    result = module.apply_local_delivery_objective(
        ctx=ctx,
        order_instance=order_instance,
        route_plan=delivery_plan,
        plan_objective="local_delivery",
    )

    for action in result.post_flush_actions:
        action()

    serialized = result.serialize_bundle()["order_stops"]
    assert len(serialized) == 2
    assert {entry["id"] for entry in serialized} == {1, 2}


def test_non_optimized_routes_are_incrementally_refreshed(monkeypatch):
    ctx = DummyCtx()
    order_instance, predecessor, created, route_solution, delivery_plan, local_delivery_plan = _setup_fixture(
        is_optimized=IS_OPTIMIZED_NOT_OPTIMIZED
    )

    monkeypatch.setattr(
        module,
        "serialize_route_solution",
        lambda route_solution: {"id": route_solution.id, "client_id": "route_10"},
    )
    monkeypatch.setattr(module, "_get_route_group", lambda *_, **__: local_delivery_plan)
    monkeypatch.setattr(
        module,
        "build_route_solution_stops",
        lambda *args, **kwargs: ([created], [(created, order_instance)], [route_solution]),
    )

    calls = {"count": 0}

    def _refresh(**kwargs):
        calls["count"] += 1
        return [predecessor, created]

    monkeypatch.setattr(sync_module, "refresh_route_solution_incremental", _refresh)

    result = module.apply_local_delivery_objective(
        ctx=ctx,
        order_instance=order_instance,
        route_plan=delivery_plan,
        plan_objective="local_delivery",
    )

    for action in result.post_flush_actions:
        action()

    serialized = result.serialize_bundle()["order_stops"]
    assert len(serialized) == 2
    assert {entry["id"] for entry in serialized} == {1, 2}
    assert calls["count"] == 1
