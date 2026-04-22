from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed


@dataclass
class LogisticLocationPayload:
    id: str
    location: str
    updated_at: str


@dataclass
class ItemPlacedRequest:
    event: str
    shop_id: str
    scan_history_id: str
    order_id: str
    item_sku: str
    logistic_location: LogisticLocationPayload


def parse_item_placed_request(raw: dict) -> ItemPlacedRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Request body must be a JSON object.")

    event = raw.get("event")
    if event != "item_placed":
        raise ValidationFailed(f"Unsupported event type: {event!r}")

    for required in ("shopId", "scanHistoryId", "orderId", "itemSku", "logisticLocation"):
        if required not in raw:
            raise ValidationFailed(f"Missing required field: {required}")

    location_raw = raw["logisticLocation"]
    if not isinstance(location_raw, dict):
        raise ValidationFailed("logisticLocation must be an object.")
    if "location" not in location_raw:
        raise ValidationFailed("logisticLocation.location is required.")

    return ItemPlacedRequest(
        event=event,
        shop_id=str(raw["shopId"]),
        scan_history_id=str(raw["scanHistoryId"]),
        order_id=str(raw["orderId"]),
        item_sku=str(raw["itemSku"]),
        logistic_location=LogisticLocationPayload(
            id=str(location_raw.get("id", "")),
            location=str(location_raw["location"]),
            updated_at=str(location_raw.get("updatedAt", "")),
        ),
    )
