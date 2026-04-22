# Shopify Intent SKU -> Order Plan Objective - Implementation Summary

Status: IMPLEMENTED
Date: 2026-04-22
Source plan archived from `docs/under_development` to `docs/archive/SHOPIFY_INTENT_SKU_PLAN_OBJECTIVE_2026-04-22.md`.

## Summary

Implemented Shopify inbound order classification based on reserved line-item SKUs.

The Shopify `orders/create` ingestion flow now:

1. Reads reserved `INTENT_*` SKUs from raw Shopify line items
2. Resolves the internal `order_plan_objective` before order creation
3. Removes all reserved SKUs from the order item payload
4. Suppresses order creation entirely when Shopify signals `INTENT_CUSTOMER_TOOK_IT`
5. Defaults to `local_delivery` when no intent SKU is present

No new plan-objective values were introduced. The implementation uses the existing internal values:

- `local_delivery`
- `store_pickup`
- `international_shipping`

## Delivered changes

### 1. New domain helper for Shopify intent resolution

Added:

- `Delivery_app_BK/services/domain/order/shopify_intent_sku.py`

Responsibilities implemented:

- Defines `INTENT_SKU_TO_PLAN_OBJECTIVE`
- Defines `FLAG_SKUS_TO_EXCLUDE`
- Defines `DEFAULT_PLAN_OBJECTIVE = "local_delivery"`
- Normalizes Shopify SKUs with trim + uppercase handling
- Resolves the first matching intent SKU from raw line items
- Returns suppression for `INTENT_CUSTOMER_TOOK_IT`
- Ignores flag SKUs during intent detection
- Falls back to `local_delivery` when no intent SKU is found

Implemented intent mapping:

- `INTENT_LOCAL_DELIVERY` -> `local_delivery`
- `INTENT_STORE_PICKUP` -> `store_pickup`
- `INTENT_INTERNATIONAL_SHIPPING` -> `international_shipping`
- `INTENT_CUSTOMER_TOOK_IT` -> suppress order creation

Implemented reserved flag exclusion:

- `FLAG_NEEDS_FIXING`

### 2. Shopify inbound order creation wiring

Updated:

- `Delivery_app_BK/services/commands/integration_shopify/ingestions/inbound/create_internal_order.py`

Behavior added:

- Reads Shopify `line_items` and resolves plan objective through the new domain helper
- Returns early without calling `create_order(...)` when `INTENT_CUSTOMER_TOOK_IT` is present
- Builds the reserved-SKU set from both intent SKUs and flag SKUs
- Filters mapped order items by `article_number` so reserved SKUs never become internal order items
- Writes `order["order_plan_objective"]` before building the `ServiceContext`

This keeps the implementation localized to the Shopify inbound path and leaves the rest of the order creation pipeline unchanged.

## Files changed

Added:

- `Delivery_app_BK/services/domain/order/shopify_intent_sku.py`
- `tests/unit/services/domain/order/test_shopify_intent_sku.py`
- `docs/implemented/SHOPIFY_INTENT_SKU_PLAN_OBJECTIVE_IMPLEMENTATION_2026-04-22.md`

Updated:

- `Delivery_app_BK/services/commands/integration_shopify/ingestions/inbound/create_internal_order.py`
- `tests/unit/services/commands/integration_shopify/test_create_internal_order.py`

Archived:

- `docs/archive/SHOPIFY_INTENT_SKU_PLAN_OBJECTIVE_2026-04-22.md`

## Behavior now in effect

### Order objective resolution

- First matching reserved intent SKU wins
- Flag SKUs do not influence routing
- Missing intent SKU defaults to `local_delivery`

### Reserved item stripping

The following line items are removed before internal order creation:

- All `INTENT_*` items
- All configured `FLAG_*` items

This ensures reserved signaling items do not enter the internal item model as physical products.

### Suppression flow

If any line item carries `INTENT_CUSTOMER_TOOK_IT`:

- the inbound command returns early
- no internal order is created
- no downstream plan-objective handling is triggered

## Tests added and updated

Updated command-level tests:

- `tests/unit/services/commands/integration_shopify/test_create_internal_order.py`

Coverage added:

- default `local_delivery` assignment when no intent SKU exists
- reserved SKU filtering from created order items
- `store_pickup` objective assignment from intent SKU
- suppression of order creation for `INTENT_CUSTOMER_TOOK_IT`

Added pure-domain tests:

- `tests/unit/services/domain/order/test_shopify_intent_sku.py`

Coverage added:

- default fallback behavior
- flag-SKU skipping during intent detection
- suppression behavior for `INTENT_CUSTOMER_TOOK_IT`

## Explicitly unchanged

No changes were made to:

- `order_mapper`
- `item_mapper`
- `Delivery_app_BK/services/commands/order/create_order.py`
- `Delivery_app_BK/services/domain/order/plan_objective_labels.py`
- plan-objective handlers and downstream workspace orchestration

This matches the original plan boundaries.

## Verification

Verified:

- Python syntax compilation passed via `python3 -m py_compile` on the touched implementation and test files

Not executed in this environment:

- `pytest`

Reason:

- the available Python environment does not have `pytest` installed (`No module named pytest`)

## Outcome

The Shopify inbound order path now respects merchant fulfillment intent encoded in reserved SKUs, prevents reserved control items from leaking into internal order items, and correctly suppresses orders that should never be created.
