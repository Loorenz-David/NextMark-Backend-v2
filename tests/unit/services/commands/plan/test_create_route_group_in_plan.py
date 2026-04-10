from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan import create_route_group_in_plan as module


class _QueryFirst:
    def __init__(self, result):
        self._result = result

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._result


def _ctx(incoming_data=None):
    return SimpleNamespace(team_id=1, incoming_data=incoming_data or {})


def test_create_manual_no_zone_route_group_uses_route_solution_defaults(monkeypatch):
    route_plan = SimpleNamespace(
        id=42,
        team_id=1,
        start_date=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    request = SimpleNamespace(
        route_plan_id=42,
        zone_id=None,
        route_group_defaults={
            "name": "Overflow",
            "route_solution": {"set_start_time": "08:15"},
        },
    )

    monkeypatch.setattr(module, "parse_create_route_group_request", lambda *_args, **_kwargs: request)
    monkeypatch.setattr(module.db.session, "get", lambda model, pk: route_plan)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    monkeypatch.setattr(module, "recompute_route_group_totals", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "serialize_route_group", lambda rg, _ctx: {"zone_snapshot": rg.zone_geometry_snapshot})

    result = module.create_route_group_in_plan(
        _ctx({"route_plan_id": 42, "name": "Overflow", "route_group_defaults": request.route_group_defaults})
    )

    assert result["created"] is True
    assert result["route_group"]["zone_snapshot"]["name"] == "Overflow"
    assert result["route_solution"]["set_start_time"] == "08:15"


def test_create_zone_route_group_returns_existing_idempotently(monkeypatch):
    route_plan = SimpleNamespace(
        id=42,
        team_id=1,
        start_date=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    zone = SimpleNamespace(id=7, team_id=1, is_active=True)
    existing_solution = SimpleNamespace(
        id=501,
        client_id="rs_501",
        is_selected=True,
        is_optimized="not optimize",
        route_group_id=77,
        start_location=None,
        end_location=None,
        set_start_time="09:00",
        set_end_time=None,
        eta_tolerance_seconds=0,
        stops_service_time=None,
    )
    existing_group = SimpleNamespace(
        id=77,
        team_id=1,
        route_plan_id=42,
        zone_id=7,
        route_solutions=[existing_solution],
    )
    request = SimpleNamespace(route_plan_id=42, zone_id=7, route_group_defaults={})

    def _fake_get(model, pk):
        if model is module.RoutePlan:
            return route_plan
        if model is module.Zone:
            return zone
        return None

    monkeypatch.setattr(module, "parse_create_route_group_request", lambda *_args, **_kwargs: request)
    monkeypatch.setattr(module.db.session, "get", _fake_get)
    monkeypatch.setattr(module, "RouteGroup", SimpleNamespace(query=_QueryFirst(existing_group)))
    monkeypatch.setattr(module, "serialize_route_group", lambda rg, _ctx: {"id": rg.id, "zone_id": rg.zone_id})

    result = module.create_route_group_in_plan(_ctx({"route_plan_id": 42, "zone_id": 7}))

    assert result["created"] is False
    assert result["route_group"] == {"id": 77, "zone_id": 7}
    assert result["route_solution"]["id"] == 501
