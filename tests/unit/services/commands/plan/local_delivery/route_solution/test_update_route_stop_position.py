import importlib
from types import SimpleNamespace

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
)

module = importlib.import_module(
    "Delivery_app_BK.services.commands.route_plan.local_delivery."
    "route_solution.stops.update_route_stop_position"
)


def _make_stop(stop_id: int, order_id: int, stop_order: int):
    return SimpleNamespace(
        id=stop_id,
        order_id=order_id,
        route_solution_id=996,
        stop_order=stop_order,
        eta_status="valid",
        expected_arrival_time=None,
        expected_departure_time=None,
    )


def test_stages_occupied_positions_before_route_timing_refresh(monkeypatch):
    moving_stop = _make_stop(6115, 101, 1)
    shifted_stop = _make_stop(6114, 102, 2)
    route_solution = SimpleNamespace(
        id=996,
        stops=[moving_stop, shifted_stop],
        is_optimized=IS_OPTIMIZED_NOT_OPTIMIZED,
        team_id=5,
    )
    ctx = SimpleNamespace(
        time_zone="Europe/Stockholm",
        user_id=None,
        set_warning=lambda _warning: None,
    )
    calls = []

    def _get_instance(*, model, value, **_kwargs):
        if model is RouteSolutionStop:
            assert value == moving_stop.id
            return moving_stop
        if model is RouteSolution:
            assert value == route_solution.id
            return route_solution
        raise AssertionError(f"Unexpected model: {model}")

    def _stage(stops):
        calls.append(("stage", [(stop.id, stop.stop_order) for stop in stops]))

    def _refresh(**_kwargs):
        calls.append(
            (
                "refresh",
                [(stop.id, stop.stop_order) for stop in route_solution.stops],
            )
        )
        return []

    session = SimpleNamespace(
        add=lambda _value: None,
        add_all=lambda _values: None,
        commit=lambda: calls.append(("commit", None)),
    )

    monkeypatch.setattr(module, "get_instance", _get_instance)
    monkeypatch.setattr(module, "_is_route_solution_end_date_valid", lambda _route: None)
    monkeypatch.setattr(
        module,
        "_validate_route_solution_orders_have_coordinates",
        lambda _route: None,
    )
    monkeypatch.setattr(module, "_orders_by_id_for_route_solution", lambda _route: {})
    monkeypatch.setattr(module, "stage_route_solution_stop_order_updates", _stage)
    monkeypatch.setattr(module, "refresh_route_solution_incremental", _refresh)
    monkeypatch.setattr(module, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(module, "create_route_solution_stop_event", lambda **_kwargs: None)
    monkeypatch.setattr(module, "emit_route_solution_stop_updated", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "notify_route_solution_stops_batch_updated",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(module, "serialize_route_solutions", lambda *_args: [])
    monkeypatch.setattr(module, "serialize_route_solution_stops", lambda *_args: [])

    module.update_route_stop_position(ctx, moving_stop.id, 2)

    assert calls == [
        ("stage", [(6115, 2), (6114, 1)]),
        ("refresh", [(6115, 2), (6114, 1)]),
        ("commit", None),
    ]
