from datetime import datetime, timezone

from Delivery_app_BK.services.commands.order.client_form import get_client_form as module


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
        "config": {
            "terms": None,
            "require_terms_acceptance": False,
            "rules": [],
            "media": {},
        },
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
