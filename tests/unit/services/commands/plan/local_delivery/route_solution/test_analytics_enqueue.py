from datetime import datetime, timezone
import importlib
from types import SimpleNamespace

select_module = importlib.import_module(
    "Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.select_route_solution"
)
mark_module = importlib.import_module(
    "Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.mark_route_solution_actual_end_time"
)


def test_select_route_solution_enqueues_compute_route_metrics_job(monkeypatch):
    route = SimpleNamespace(id=77, team_id=10, route_group_id=55, is_selected=True)
    captured = {"job": None}

    monkeypatch.setattr(select_module, "get_instance", lambda **_kwargs: route)
    monkeypatch.setattr(
        select_module,
        "ensure_single_selected_route_solution",
        lambda _plan_id, preferred_route_solution_id: [route],
    )
    monkeypatch.setattr(
        select_module,
        "db",
        SimpleNamespace(session=SimpleNamespace(add_all=lambda _rows: None, commit=lambda: None)),
    )
    monkeypatch.setattr(
        select_module,
        "enqueue_job",
        lambda **kwargs: captured.__setitem__("job", kwargs),
    )
    monkeypatch.setattr(select_module, "create_route_solution_event", lambda **_kwargs: None)
    monkeypatch.setattr(select_module, "emit_route_solution_updated", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        select_module,
        "build_create_result",
        lambda _ctx, _rows, extract_fields: [{"id": route.id, "is_selected": True}],
    )

    result = select_module.select_route_solution(SimpleNamespace(), route_solution_id=route.id)

    assert result["route_solution"][0]["id"] == route.id
    assert captured["job"] is not None
    assert captured["job"]["description"] == f"analytics:route_metrics:{route.id}"
    assert captured["job"]["args"] == (route.id,)


def test_mark_actual_end_time_enqueues_compute_route_metrics_job(monkeypatch):
    route = SimpleNamespace(id=88, team_id=11, actual_end_time=None)
    captured = {"job": None}
    resolved_time = datetime(2026, 3, 25, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(mark_module, "get_instance", lambda **_kwargs: route)
    monkeypatch.setattr(
        mark_module,
        "parse_mark_actual_time_request",
        lambda _request: SimpleNamespace(time="2026-03-25T12:00:00+00:00"),
    )
    monkeypatch.setattr(mark_module, "resolve_actual_timestamp", lambda _time: resolved_time)
    monkeypatch.setattr(
        mark_module,
        "db",
        SimpleNamespace(session=SimpleNamespace(add=lambda _row: None, commit=lambda: None)),
    )
    monkeypatch.setattr(
        mark_module,
        "enqueue_job",
        lambda **kwargs: captured.__setitem__("job", kwargs),
    )
    monkeypatch.setattr(mark_module, "create_route_solution_event", lambda **_kwargs: None)
    monkeypatch.setattr(mark_module, "emit_route_solution_updated", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mark_module, "serialize_route_solutions", lambda _rows, _ctx: [{"id": route.id}])

    result = mark_module.mark_route_solution_actual_end_time(
        SimpleNamespace(),
        route_solution_id=route.id,
        request={"time": "2026-03-25T12:00:00+00:00"},
    )

    assert route.actual_end_time == resolved_time
    assert result["route_solution"][0]["id"] == route.id
    assert captured["job"] is not None
    assert captured["job"]["description"] == f"analytics:route_metrics:{route.id}"
    assert captured["job"]["args"] == (route.id,)
