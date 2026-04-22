from Delivery_app_BK.services.domain.order.shopify_intent_sku import (
    DEFAULT_PLAN_OBJECTIVE,
    resolve_intent_from_shopify_line_items,
)


def test_resolve_intent_from_shopify_line_items_defaults_to_local_delivery():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "SKU-1"},
            {"sku": None},
        ]
    ) == (DEFAULT_PLAN_OBJECTIVE, False)


def test_resolve_intent_from_shopify_line_items_skips_flag_skus():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "FLAG_NEEDS_FIXING"},
            {"sku": " intent_international_shipping "},
        ]
    ) == ("international_shipping", False)


def test_resolve_intent_from_shopify_line_items_suppresses_customer_took_it():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "INTENT_CUSTOMER_TOOK_IT"},
            {"sku": "INTENT_LOCAL_DELIVERY"},
        ]
    ) == (None, True)
