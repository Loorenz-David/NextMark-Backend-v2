import importlib
from datetime import datetime, timezone
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.commands.drivers.mark_driver_stop_actual_arrival_time"
)


def test_mark_driver_stop_actual_arrival_time_backfills_route_start_and_enqueues_analytics(monkeypatch):
    route_plan = SimpleNamespace(id=90)
    route_solution = SimpleNamespace(
        id=731,
        team_id=1,
        route_group=SimpleNamespace(route_plan=route_plan),
        actual_start_time=None,
    )
    route_stop = SimpleNamespace(
        id=81,
        team_id=1,
        route_solution_id=731,
        actual_arrival_time=None,
        client_id="route_stop_abc",
    )
    candidate_time = datetime(2026, 4, 21, 10, 5, tzinfo=timezone.utc)

    monkeypatch.setattr(module, "parse_driver_observed_time_request", lambda request: request)
    monkeypatch.setattr(module, "resolve_driver_route_stop", lambda ctx, stop_client_id: route_stop)
    monkeypatch.setattr(module, "resolve_driver_route_solution", lambda ctx, route_id: route_solution)
    monkeypatch.setattr(module, "resolve_candidate_timestamp", lambda observed_time: candidate_time)
    monkeypatch.setattr(module, "can_record_route_timestamp", lambda route, ts: True)
    monkeypatch.setattr(module, "ensure_route_solution_actual_start_time", lambda route, ts: setattr(route, "actual_start_time", ts) or True)
    monkeypatch.setattr(module, "apply_plan_state", lambda plan, state_id: None)
    monkeypatch.setattr(module, "serialize_driver_stop_timing_command_delta", lambda stop: {"id": stop.id, "actual_arrival_time": stop.actual_arrival_time})
    monkeypatch.setattr(module, "serialize_driver_route_timing_command_delta", lambda route: {"id": route.id, "actual_start_time": route.actual_start_time})
    monkeypatch.setattr(module, "create_route_solution_stop_event", lambda **kwargs: None)
    monkeypatch.setattr(module, "emit_route_solution_stop_updated", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "create_route_solution_event", lambda **kwargs: None)
    monkeypatch.setattr(module, "emit_route_solution_updated", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "build_timing_result", lambda **kwargs: kwargs)

    enqueued = {}
    added = []
    monkeypatch.setattr(
        module,
        "enqueue_job",
        lambda **kwargs: enqueued.update(kwargs),
    )
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(
            session=SimpleNamespace(
                add=lambda instance: added.append(instance),
                commit=lambda: None,
                get=lambda *_args, **_kwargs: None,
            )
        ),
    )

    result = module.mark_driver_stop_actual_arrival_time(
        SimpleNamespace(user_id=1),
        "route_stop_abc",
        SimpleNamespace(observed_time=None),
    )

    assert route_stop.actual_arrival_time is candidate_time
    assert route_solution.actual_start_time is candidate_time
    assert result["recorded"] is True
    assert result["route"] == {"id": 731, "actual_start_time": candidate_time}
    assert enqueued["args"] == (731,)
