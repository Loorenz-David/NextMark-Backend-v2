from datetime import datetime, timezone

from Delivery_app_BK.services.commands.order.client_form import get_client_form as module


def _plan_stub(*, date_strategy, start_date, end_date):
    return type(
        "RoutePlanStub",
        (),
        {
            "date_strategy": date_strategy,
            "start_date": start_date,
            "end_date": end_date,
        },
    )()


def test_get_client_form_data_serializes_items_using_item_type(monkeypatch):
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 101,
            "reference_number": "REF-101",
            "external_source": "shopify",
            "team_id": 7,
            "team": type("TeamStub", (), {"name": "Demo Team", "time_zone": "Europe/Stockholm"})(),
            "items": [
                type("ItemStub", (), {"item_type": "Chair", "quantity": 2})(),
                type("ItemStub", (), {"item_type": "Lamp", "quantity": 1})(),
            ],
            "client_form_token_expires_at": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            "route_plan": None,
        },
    )()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(
        module,
        "build_public_client_form_config",
        lambda team_id: {"terms": None, "require_terms_acceptance": False, "rules": [], "media": {}},
    )

    result = module.get_client_form_data("token123")

    assert result == {
        "order_scalar_id": 101,
        "reference_number": "REF-101",
        "external_source": "shopify",
        "team_timezone": "Europe/Stockholm",
        "items": [
            {"item_type": "Chair", "quantity": 2},
            {"item_type": "Lamp", "quantity": 1},
        ],
        "expires_at": "2026-04-11T12:00:00+00:00",
        "route_plan_schedule": None,
        "config": {
            "terms": None,
            "require_terms_acceptance": False,
            "rules": [],
            "media": {},
        },
    }


def test_get_client_form_data_includes_route_plan_schedule_when_plan_assigned(monkeypatch):
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 202,
            "reference_number": "REF-202",
            "external_source": "manual",
            "team_id": 7,
            "team": type("TeamStub", (), {"name": "T", "time_zone": "UTC"})(),
            "items": [],
            "client_form_token_expires_at": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            "route_plan": _plan_stub(
                date_strategy="range",
                start_date=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                end_date=datetime(2026, 5, 3, 20, 0, tzinfo=timezone.utc),
            ),
        },
    )()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "build_public_client_form_config", lambda team_id: {"rules": []})

    result = module.get_client_form_data("token123")

    assert result["route_plan_schedule"] == {
        "date_strategy": "range",
        "start_date": "2026-05-01T08:00:00+00:00",
        "end_date": "2026-05-03T20:00:00+00:00",
    }


def test_get_client_form_data_single_strategy_keeps_end_date_as_stored(monkeypatch):
    """A single-strategy plan auto-populates end_date; it must be sent as-is, not nulled."""
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 203,
            "reference_number": "REF-203",
            "external_source": "manual",
            "team_id": 7,
            "team": type("TeamStub", (), {"name": "T", "time_zone": "UTC"})(),
            "items": [],
            "client_form_token_expires_at": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            "route_plan": _plan_stub(
                date_strategy="single",
                start_date=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                end_date=datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
            ),
        },
    )()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "build_public_client_form_config", lambda team_id: {"rules": []})

    result = module.get_client_form_data("token123")

    assert result["route_plan_schedule"] == {
        "date_strategy": "single",
        "start_date": "2026-05-01T00:00:00+00:00",
        "end_date": "2026-05-01T23:59:59+00:00",
    }


def test_get_client_form_data_guards_null_dates_on_assigned_plan(monkeypatch):
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 204,
            "reference_number": "REF-204",
            "external_source": "manual",
            "team_id": 7,
            "team": type("TeamStub", (), {"name": "T", "time_zone": "UTC"})(),
            "items": [],
            "client_form_token_expires_at": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            "route_plan": _plan_stub(date_strategy="range", start_date=None, end_date=None),
        },
    )()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "build_public_client_form_config", lambda team_id: {"rules": []})

    result = module.get_client_form_data("token123")

    assert result["route_plan_schedule"] == {
        "date_strategy": "range",
        "start_date": None,
        "end_date": None,
    }


def test_get_client_form_data_scopes_config_to_the_token_resolved_team(monkeypatch):
    """The form config must follow the order's team — never a caller-supplied id."""
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 7,
            "reference_number": "REF-7",
            "external_source": "manual",
            "team_id": 55,
            "team": type("TeamStub", (), {"name": "T", "time_zone": "UTC"})(),
            "items": [],
            "client_form_token_expires_at": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            "route_plan": None,
        },
    )()

    requested_team_ids: list[int] = []

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(
        module,
        "build_public_client_form_config",
        lambda team_id: requested_team_ids.append(team_id) or {"rules": []},
    )

    module.get_client_form_data("token123")

    assert requested_team_ids == [55]
