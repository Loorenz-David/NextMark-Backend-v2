from Delivery_app_BK.services.domain.order.shopify_intent_sku import (
    DEFAULT_PLAN_OBJECTIVE,
    ShopifyIntentResolution,
    resolve_intent_from_shopify_line_items,
)


def test_resolve_intent_from_shopify_line_items_defaults_to_local_delivery():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "SKU-1"},
            {"sku": None},
        ]
    ) == ShopifyIntentResolution(plan_objective=DEFAULT_PLAN_OBJECTIVE, is_unplanned=False)


def test_resolve_intent_from_shopify_line_items_skips_flag_skus():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "FLAG_NEEDS_FIXING"},
            {"sku": " intent_international_shipping "},
        ]
    ) == ShopifyIntentResolution(plan_objective="international_shipping", is_unplanned=False)


def test_resolve_intent_from_shopify_line_items_marks_customer_took_it_unplanned():
    assert resolve_intent_from_shopify_line_items(
        [
            {"sku": "INTENT_CUSTOMER_TOOK_IT"},
            {"sku": "INTENT_LOCAL_DELIVERY"},
        ]
    ) == ShopifyIntentResolution(plan_objective=None, is_unplanned=True)
