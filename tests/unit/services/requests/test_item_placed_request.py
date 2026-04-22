import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import (
    parse_item_placed_request,
)


def test_parse_item_placed_request_accepts_valid_payload():
    parsed = parse_item_placed_request(
        {
            "event": "item_placed",
            "shopId": "shop-abc-123",
            "scanHistoryId": "scan-456",
            "orderId": "ord-client-789",
            "itemSku": "SKU-RED-XL",
            "logisticLocation": {
                "id": "loc-001",
                "location": "Shelf A-3",
                "updatedAt": "2026-04-22T10:30:00Z",
            },
        }
    )

    assert parsed.event == "item_placed"
    assert parsed.order_id == "ord-client-789"
    assert parsed.item_sku == "SKU-RED-XL"
    assert parsed.logistic_location.location == "Shelf A-3"


def test_parse_item_placed_request_rejects_wrong_event_type():
    with pytest.raises(ValidationFailed):
        parse_item_placed_request({"event": "other"})


def test_parse_item_placed_request_rejects_missing_location():
    with pytest.raises(ValidationFailed):
        parse_item_placed_request(
            {
                "event": "item_placed",
                "shopId": "shop-abc-123",
                "scanHistoryId": "scan-456",
                "orderId": "ord-client-789",
                "itemSku": "SKU-RED-XL",
                "logisticLocation": {},
            }
        )
