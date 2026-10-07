from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.local_delivery import (
    update_settings as module,
)


def _make_route_patch():
    return SimpleNamespace(
        route_solution_id=10,
        start_location=None,
        end_location=None,
        set_start_time=None,
        set_end_time=None,
        route_end_strategy=None,
        driver_id=None,
        has_start_location=False,
        has_end_location=False,
        has_set_start_time=False,
        has_set_end_time=False,
        has_route_end_strategy=False,
        has_driver_id=False,
    )


def _make_request(time_zone):
    return SimpleNamespace(
        route_group_id=1,
        create_variant_on_save=False,
        time_zone=time_zone,
        route_plan=SimpleNamespace(),
        route_solution=_make_route_patch(),
    )


def test_update_local_delivery_settings_uses_identity_timezone_when_missing_in_payload(monkeypatch):
    captured = {}
    now = datetime.now(timezone.utc)
    request = _make_request(time_zone=None)
    route_plan = SimpleNamespace(id=2, start_date=now, end_date=now)
    route_group = SimpleNamespace(id=1)
    route_solution = SimpleNamespace(id=10, stops=[])

    monkeypatch.setattr(
        module,
        "parse_update_local_delivery_settings_request",
        lambda raw: request,
    )
    monkeypatch.setattr(
        module,
        "load_route_group_settings_entities",
        lambda ctx, request: (route_group, route_plan, route_solution),
    )
    monkeypatch.setattr(
        module,
        "apply_route_plan_patch",
        lambda route_plan, patch: (route_plan.start_date, route_plan.end_date, []),
    )

    def _fake_update_route_solution_from_plan(**kwargs):
        captured["time_zone"] = kwargs.get("time_zone")
        return route_solution, False, None

    monkeypatch.setattr(module, "update_route_solution_from_route_plan", _fake_update_route_solution_from_plan)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "add_all", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "emit_pending_route_plan_events", lambda ctx, events: None)
    monkeypatch.setattr(
        module,
        "build_route_group_settings_response",
        lambda ctx, route_solution, stops_changed, route_solution_changed: {},
    )

    module.update_local_delivery_settings(
        SimpleNamespace(
            incoming_data={},
            time_zone="America/New_York",
            set_warning=lambda message: None,
        )
    )

    assert captured["time_zone"] == "America/New_York"


def test_update_local_delivery_settings_uses_context_timezone_even_when_payload_has_timezone(monkeypatch):
    captured = {}
    now = datetime.now(timezone.utc)
    request = _make_request(time_zone="Europe/Stockholm")
    route_plan = SimpleNamespace(id=2, start_date=now, end_date=now)
    route_group = SimpleNamespace(id=1)
    route_solution = SimpleNamespace(id=10, stops=[])

    monkeypatch.setattr(
        module,
        "parse_update_local_delivery_settings_request",
        lambda raw: request,
    )
    monkeypatch.setattr(
        module,
        "load_route_group_settings_entities",
        lambda ctx, request: (route_group, route_plan, route_solution),
    )
    monkeypatch.setattr(
        module,
        "apply_route_plan_patch",
        lambda route_plan, patch: (route_plan.start_date, route_plan.end_date, []),
    )

    def _fake_update_route_solution_from_plan(**kwargs):
        captured["time_zone"] = kwargs.get("time_zone")
        return route_solution, False, None

    monkeypatch.setattr(module, "update_route_solution_from_route_plan", _fake_update_route_solution_from_plan)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "add_all", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "emit_pending_route_plan_events", lambda ctx, events: None)
    monkeypatch.setattr(
        module,
        "build_route_group_settings_response",
        lambda ctx, route_solution, stops_changed, route_solution_changed: {},
    )

    module.update_local_delivery_settings(
        SimpleNamespace(
            incoming_data={},
            time_zone="America/New_York",
            set_warning=lambda message: None,
        )
    )

    assert captured["time_zone"] == "America/New_York"


def test_moving_plan_dates_reschedules_every_order_quietly():
    team_id = 10
    order_one = SimpleNamespace(id=1, team_id=team_id)
    order_two = SimpleNamespace(id=2, team_id=team_id)
    route_plan = SimpleNamespace(
        start_date=datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 2, 23, 0, tzinfo=timezone.utc),
        orders=[order_one, order_two],
    )

    events = module._build_plan_window_rescheduled_events(
        ctx=SimpleNamespace(team_id=team_id),
        route_plan=route_plan,
        previous_plan_start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        previous_plan_end=datetime(2026, 3, 1, 23, 0, tzinfo=timezone.utc),
    )

    assert {event["order_id"] for event in events} == {1, 2}
    assert {event["payload"]["reason"] for event in events} == {"plan_window_changed"}
    # The plan's own notification reports the move.
    assert all(event["payload"]["notification_suppressed"] for event in events)


def test_unchanged_plan_dates_reschedule_nothing():
    route_plan = SimpleNamespace(
        start_date=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 1, 23, 0, tzinfo=timezone.utc),
        orders=[SimpleNamespace(id=1, team_id=10)],
    )

    assert module._build_plan_window_rescheduled_events(
        ctx=SimpleNamespace(team_id=10),
        route_plan=route_plan,
        previous_plan_start=route_plan.start_date,
        previous_plan_end=route_plan.end_date,
    ) == []
