from datetime import datetime, timezone

from Delivery_app_BK.services.commands.order.client_form import get_client_form as module


def test_get_client_form_data_serializes_items_using_item_type(monkeypatch):
    order = type(
        "OrderStub",
        (),
        {
            "order_scalar_id": 101,
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

    result = module.get_client_form_data("token123")

    assert result == {
        "order_scalar_id": 101,
        "team_timezone": "Europe/Stockholm",
        "items": [
            {"name": "Chair", "quantity": 2},
            {"name": "Lamp", "quantity": 1},
        ],
        "expires_at": "2026-04-11T12:00:00+00:00",
    }
