from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    normalize_local_delivery_route_solution_defaults,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync.window import (
    resolve_window,
)


def test_normalize_local_delivery_route_solution_defaults_builds_expected_start_in_utc():
    ctx = SimpleNamespace(identity={"time_zone": "Europe/Stockholm"}, team_id=3)
    plan_instance = SimpleNamespace(
        start_date=datetime(2026, 3, 7, 0, 0, 0, tzinfo=timezone.utc),
        team_id=3,
    )

    normalized = normalize_local_delivery_route_solution_defaults(
        ctx,
        plan_instance,
        {
            "route_solution": {
                "set_start_time": "17:00",
            }
        },
    )

    assert normalized["set_start_time"] == "17:00"
    assert normalized["expected_start_time"] == datetime(
        2026, 3, 7, 16, 0, 0, tzinfo=timezone.utc
    )


def test_normalize_local_delivery_route_solution_defaults_preserves_create_defaults():
    ctx = SimpleNamespace(identity={"time_zone": "Europe/Stockholm"}, team_id=3)
    plan_instance = SimpleNamespace(
        start_date=datetime(2026, 5, 2, 0, 0, 0, tzinfo=timezone.utc),
        team_id=3,
    )

    normalized = normalize_local_delivery_route_solution_defaults(
        ctx,
        plan_instance,
        {
            "route_solution": {
                "set_start_time": "09:55",
                "set_end_time": "22:59",
                "eta_tolerance_seconds": 0,
                "eta_message_tolerance": 1200,
                "route_end_strategy": "round_trip",
                "driver_id": 3,
                "vehicle_id": 7,
                "stops_service_time": {"time": 180, "per_item": 120},
            }
        },
    )

    assert normalized["set_start_time"] == "09:55"
    assert normalized["set_end_time"] == "22:59"
    assert normalized["eta_tolerance_seconds"] == 0
    assert normalized["eta_message_tolerance"] == 1200
    assert normalized["route_end_strategy"] == "round_trip"
    assert normalized["driver_id"] == 3
    assert normalized["vehicle_id"] == 7
    assert normalized["stops_service_time"] == {"time": 180, "per_item": 120}


def test_resolve_window_treats_route_times_as_team_local_wall_clock():
    window = resolve_window(
        plan_start=datetime(2026, 3, 7, 0, 0, 0, tzinfo=timezone.utc),
        plan_end=datetime(2026, 3, 7, 23, 59, 59, tzinfo=timezone.utc),
        set_start_time="17:00",
        set_end_time="21:00",
        time_zone="Europe/Stockholm",
    )

    assert window == (
        datetime(2026, 3, 7, 16, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 7, 20, 0, 0, tzinfo=timezone.utc),
    )
