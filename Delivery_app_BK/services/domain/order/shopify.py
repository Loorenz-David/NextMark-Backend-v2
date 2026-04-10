from __future__ import annotations

from typing import Any


SHOPIFY_EXTERNAL_SOURCE = "shopify"
SHOPIFY_ORDER_COSTUMER_EDIT_FIELDS = {
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
}


def is_shopify_order(order: Any) -> bool:
    return (
        getattr(order, "external_source", None) == SHOPIFY_EXTERNAL_SOURCE
        and bool(getattr(order, "external_order_id", None))
    )


def has_shopify_order_costumer_field_changes(submitted_fields: dict[str, Any] | None) -> bool:
    if not isinstance(submitted_fields, dict):
        return False
    return bool(SHOPIFY_ORDER_COSTUMER_EDIT_FIELDS.intersection(submitted_fields.keys()))


def should_sync_shopify_order_costumer(order: Any, submitted_fields: dict[str, Any] | None) -> bool:
    if not is_shopify_order(order):
        return False
    if not has_shopify_order_costumer_field_changes(submitted_fields):
        return False

    costumer = getattr(order, "costumer", None)
    if costumer is None:
        return False

    return (
        getattr(costumer, "external_source", None) != SHOPIFY_EXTERNAL_SOURCE
        and not getattr(costumer, "external_costumer_id", None)
    )


def should_fulfill_shopify_order(order: Any) -> bool:
    return is_shopify_order(order)
