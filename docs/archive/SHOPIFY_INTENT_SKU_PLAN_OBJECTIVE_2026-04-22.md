# Shopify Intent SKU → Order Plan Objective Mapping

> **Problem:** The Shopify `orders/create` webhook creates internal orders without setting
> `order_plan_objective`. Merchants signal fulfillment intent via reserved product SKUs
> (`INTENT_*`) on line items. This intent is currently ignored — all orders land as
> unclassified, and the wrong plan types are used downstream. Additionally, some line items
> carry `FLAG_*` SKUs that belong to other applications and must never enter this system.
>
> **Goal:** Read reserved SKUs from the Shopify line items before order creation.
> Map `INTENT_*` SKUs to the correct `order_plan_objective`. Strip all reserved SKU items
> (both `INTENT_*` and `FLAG_*`) from the order's item list. If `INTENT_CUSTOMER_TOOK_IT`
> is present, suppress order creation entirely. If no intent SKU is found, default to
> `local_delivery`.

---

## Reserved SKU Reference

### Intent SKUs — determine `order_plan_objective`

| SKU                             | `order_plan_objective` | Notes                                      |
|---------------------------------|------------------------|--------------------------------------------|
| `INTENT_LOCAL_DELIVERY`         | `local_delivery`       | Maps to `route_plan` workspace             |
| `INTENT_STORE_PICKUP`           | `store_pickup`         | Maps to `store_pickup_plan` workspace      |
| `INTENT_INTERNATIONAL_SHIPPING` | `international_shipping` | Maps to international workspace          |
| `INTENT_CUSTOMER_TOOK_IT`       | — (suppressed)         | Order must NOT be created                  |
| *(none found)*                  | `local_delivery`       | Same default as the order creation command |

The plan objective values map to the `ORDER_PLAN_OBJECTIVES` set in
`services/domain/order/plan_objective_labels.py`. No new values are introduced.

### Flag SKUs — items that belong to other systems, always excluded

| SKU                 | Behaviour                                              |
|---------------------|--------------------------------------------------------|
| `FLAG_NEEDS_FIXING` | Item stripped from order; no effect on plan objective  |

Flag SKUs carry no routing intent and have no meaning in this application. Items with
these SKUs are silently dropped before order creation. They never affect `order_plan_objective`.

---

## Existing Architecture Anchors

### Where `order_plan_objective` is stored
`models/tables/order/order.py:39` — `order_plan_objective = Column(String, index=True)`.
The validator at line 218 already enforces only `ORDER_PLAN_OBJECTIVES` values.

### Where `order_plan_objective` is resolved on creation
`services/commands/order/create_order.py:147–151` — if `order_plan_objective` is already
set on the incoming fields dict it is preserved; the command never overwrites an explicit
value. Setting it in the inbound payload is sufficient.

### Where `ORDER_PLAN_OBJECTIVES` are declared
`services/domain/order/plan_objective_labels.py` — `ORDER_PLAN_OBJECTIVES`, aliases, and
`resolve_effective_order_plan_objective`. This is the single source of truth; the new
mapping must reference these values and nothing else.

### Current inbound flow
```
shopify router
    → create_internal_order(shop, payload)
        → order_mapper(payload)           # builds order dict from Shopify payload
        → item_mapper(item) for each item  # builds item dicts
        → order["items"] = items
        → order["order_plan_objective"] = ???  ← MISSING — this is what we add
        → ServiceContext(incoming_data={"fields": order})
        → create_order(ctx)
```

---

## What Changes

### Layer: Domain (pure Python, no I/O)

**New file:** `services/domain/order/shopify_intent_sku.py`

Single responsibility: translate a list of Shopify line items into either an
`order_plan_objective` string or a suppression signal.

```python
# Conceptual interface — Codex writes the actual code
INTENT_SKU_TO_PLAN_OBJECTIVE: dict[str, str | None] = {
    "INTENT_LOCAL_DELIVERY":          "local_delivery",
    "INTENT_STORE_PICKUP":            "store_pickup",
    "INTENT_INTERNATIONAL_SHIPPING":  "international_shipping",
    "INTENT_CUSTOMER_TOOK_IT":        None,   # None = suppress order
}

FLAG_SKUS_TO_EXCLUDE: frozenset[str] = frozenset({
    "FLAG_NEEDS_FIXING",
})

DEFAULT_PLAN_OBJECTIVE = "local_delivery"

def resolve_intent_from_shopify_line_items(
    line_items: list[dict],
) -> tuple[str | None, bool]:
    """
    Returns (plan_objective, should_suppress).

    should_suppress=True  → caller must not create the order.
    plan_objective=None and should_suppress=False → use DEFAULT_PLAN_OBJECTIVE.
    """
```

Rules for `resolve_intent_from_shopify_line_items`:
- Iterate `line_items`, read `item.get("sku")` (strip + uppercase).
- Skip items whose SKU is in `FLAG_SKUS_TO_EXCLUDE` — they are irrelevant to intent.
- First matching INTENT SKU wins (Shopify orders may have multiple line items).
- `INTENT_CUSTOMER_TOOK_IT` → return `(None, True)`.
- Any other intent SKU → return `(mapped_objective, False)`.
- No intent SKU found → return `(DEFAULT_PLAN_OBJECTIVE, False)`.
- This file must not import models, SQLAlchemy, or any service layer.

`INTENT_SKU_TO_PLAN_OBJECTIVE` and `FLAG_SKUS_TO_EXCLUDE` are kept as separate constants
because they represent distinct concerns: one is a routing map, the other is a
cross-system exclusion list. The inbound command uses both for item filtering.

---

### Layer: Inbound command (integration — not domain, not order)

**Edit:** `services/commands/integration_shopify/ingestions/inbound/create_internal_order.py`

After `item_mapper` loop, call `resolve_intent_from_shopify_line_items` and either:
- Set `order["order_plan_objective"] = plan_objective` and continue to `create_order`, or
- Return early (silently drop) if `should_suppress is True`.

All reserved SKU items — both `INTENT_*` and `FLAG_*` — must be stripped from
`order["items"]` before calling `create_order`. Neither group represents a physical product
for this application. The item mapper loop runs on all raw line items first; the filtering
step removes any mapped item whose `article_number` is in either
`INTENT_SKU_TO_PLAN_OBJECTIVE` keys or `FLAG_SKUS_TO_EXCLUDE`.

**No changes needed to:**
- `order_mapper` — it maps order-level fields only, not routing intent.
- `item_mapper` — it already reads `sku`; intent detection is a separate concern.
- `create_order` — it already respects an explicit `order_plan_objective` in the fields dict.
- Any plan objective handler (`plan_objectives/local_delivery.py`, etc.) — unchanged.
- `plan_objective_labels.py` — the values we set are already valid.

---

## File-by-File Implementation Plan

### Step 1 — Domain function (no dependencies, implement first)

**Create** `services/domain/order/shopify_intent_sku.py`:

- Define `INTENT_SKU_TO_PLAN_OBJECTIVE` mapping dict.
- Define `FLAG_SKUS_TO_EXCLUDE` as a `frozenset[str]` containing `"FLAG_NEEDS_FIXING"`.
- Define `DEFAULT_PLAN_OBJECTIVE = "local_delivery"`.
- Implement `resolve_intent_from_shopify_line_items(line_items: list[dict]) -> tuple[str | None, bool]`.
  - Flag SKUs are skipped during intent detection (not matched against `INTENT_SKU_TO_PLAN_OBJECTIVE`).
- No imports from models or services.

### Step 2 — Wire into inbound command

**Edit** `services/commands/integration_shopify/ingestions/inbound/create_internal_order.py`:

After the existing `line_items` / `items` block (currently lines 23–26), add:

```python
from Delivery_app_BK.services.domain.order.shopify_intent_sku import (
    INTENT_SKU_TO_PLAN_OBJECTIVE,
    FLAG_SKUS_TO_EXCLUDE,
    resolve_intent_from_shopify_line_items,
)

plan_objective, should_suppress = resolve_intent_from_shopify_line_items(line_items)

if should_suppress:
    return   # INTENT_CUSTOMER_TOOK_IT — order is intentionally not created

_reserved_skus = INTENT_SKU_TO_PLAN_OBJECTIVE.keys() | FLAG_SKUS_TO_EXCLUDE

# Strip all reserved SKU items — they are not physical products for this application.
items = [
    item for item in items
    if item.get("article_number") not in _reserved_skus
]

order["items"] = items
order["order_plan_objective"] = plan_objective
```

Note: `article_number` is what `item_mapper` writes from `shopify_item.get("sku")`.
The union of both sets ensures INTENT items (routing signals) and FLAG items
(foreign-system markers) are excluded in a single pass.

Place the import at the top of the file with the other imports.

---

## What Codex Must NOT Do

- Do not add `order_plan_objective` parsing inside `order_mapper` — that mapper owns
  order-level Shopify fields only.
- Do not add `order_plan_objective` parsing inside `item_mapper` — that mapper owns
  item-level field projection.
- Do not pass intent SKU items as order line items. They must be filtered out of
  `order["items"]` in `create_internal_order.py` before calling `create_order`.
- Do not introduce a new `order_plan_objective` value. Use only values from
  `ORDER_PLAN_OBJECTIVES` (`local_delivery`, `store_pickup`, `international_shipping`).
- Do not add new arguments to `create_order`. The field is passed via the existing
  `incoming_data.fields` dict.
- Do not modify `create_order.py` or any file outside the two files listed above.

---

## Blast Radius

| Scope | Impact |
|---|---|
| `create_internal_order.py` | Only Shopify inbound webhook path; zero impact on direct API order creation |
| `shopify_intent_sku.py` (new) | Pure function; no side effects; safe to add |
| `create_order.py` | No changes — already handles explicit `order_plan_objective` |
| Order model validator | No changes — only existing valid values are written |
| Existing Shopify orders | Existing stored orders unaffected — this only changes creation logic |

---

## Verification Checklist

- [ ] `INTENT_LOCAL_DELIVERY` → `order_plan_objective = "local_delivery"` on created order
- [ ] `INTENT_STORE_PICKUP` → `order_plan_objective = "store_pickup"` on created order
- [ ] `INTENT_INTERNATIONAL_SHIPPING` → `order_plan_objective = "international_shipping"` on created order
- [ ] `INTENT_CUSTOMER_TOOK_IT` → `create_internal_order` returns without calling `create_order`
- [ ] No intent SKU on any line item → `order_plan_objective = "local_delivery"` (default)
- [ ] Multiple intent SKUs on same order → first one found wins, order is created once
- [ ] Non-intent SKUs (regular products) → treated as no-intent; default applies
- [ ] Intent SKU items are absent from `order["items"]` passed to `create_order`
- [ ] `FLAG_NEEDS_FIXING` items are absent from `order["items"]` passed to `create_order`
- [ ] `FLAG_NEEDS_FIXING` items do not affect `order_plan_objective` (intent detection skips them)
- [ ] Regular product items on the same order are preserved in `order["items"]`
- [ ] `shopify_intent_sku.py` imports nothing from models or services
