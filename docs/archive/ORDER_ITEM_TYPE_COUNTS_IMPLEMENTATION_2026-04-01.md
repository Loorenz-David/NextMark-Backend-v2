# Order Item Type Counts — Implementation Plan

**Date:** 2026-04-01
**Column name:** `item_type_counts`
**Table:** `order`
**Type:** `JSONB` — `dict[str, int]` where keys are item type strings and values are total quantities

---

## Purpose

Store a denormalized snapshot of item type quantities on the `Order` row so that statistics and list previews can show composition breakdowns without loading the `items` relationship.

**Example value:**
```json
{"Dining tables": 2, "Dining chair": 8, "Sofa": 1}
```

Invariants enforced at write time:
- Only types with a total quantity ≥ 1 appear in the dict.
- Types whose summed quantity drops to 0 or below are removed.
- `None` and empty `{}` are both valid (order has no items).

---

## Files to Create or Modify

| File | Change |
|------|--------|
| `Delivery_app_BK/models/tables/order/order.py` | Add column |
| `alembic/versions/<new>.py` | Migration |
| `Delivery_app_BK/services/domain/order/recompute_order_totals.py` | Add `item_type_counts` computation |
| `Delivery_app_BK/services/commands/order/create_order.py` | Already calls `recompute_order_totals` — no change needed |
| `Delivery_app_BK/services/commands/item/create/create_item.py` | Already calls `recompute_order_totals` — no change needed |
| `Delivery_app_BK/services/commands/item/update/update_item.py` | Already calls `recompute_order_totals` — no change needed |
| `Delivery_app_BK/services/commands/item/delete/delete_item.py` | Already calls `recompute_order_totals` — no change needed |
| `Delivery_app_BK/services/queries/utils/metrics.py` | Extend `calculate_item_totals` to return `item_type_counts` |

---

## Step 1 — Column definition

**File:** `Delivery_app_BK/models/tables/order/order.py`

Add after `total_item_count`:

```python
item_type_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
```

The column is nullable. An order with no items stores `None` (not `{}`).

---

## Step 2 — Alembic migration

Generate and fill in the migration:

```bash
.venv/bin/alembic revision --autogenerate -m "add item_type_counts to order"
```

Verify the generated file adds only:
```python
op.add_column(
    "order",
    sa.Column(
        "item_type_counts",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    ),
)
```

No backfill is required at migration time. The column defaults to `NULL` for all existing rows. If a backfill of historical data is needed later it should be a separate script, not part of this migration.

---

## Step 3 — Domain function extension

**File:** `Delivery_app_BK/services/queries/utils/metrics.py`

Extend `calculate_item_totals` to compute and return `item_type_counts`:

```python
def calculate_item_totals(items: Iterable[Item]) -> dict:
    total_items = 0
    total_volume = 0.0
    total_weight = 0.0
    type_counts: dict[str, int] = {}

    for item in items:
        quantity = item.quantity or 1
        total_items += quantity
        total_volume += _item_volume_cm3(item) * quantity
        total_weight += _item_weight_g(item) * quantity

        item_type = getattr(item, "item_type", None)
        if item_type:
            type_counts[item_type] = type_counts.get(item_type, 0) + quantity

    # Remove any type whose accumulated count dropped to ≤ 0
    type_counts = {t: c for t, c in type_counts.items() if c >= 1}

    return {
        "total_items": total_items,
        "total_volume": total_volume,
        "total_weight": total_weight,
        "item_type_counts": type_counts if type_counts else None,
    }
```

The guard `if c >= 1` handles the edge case where a caller has items with zero or negative quantity stored historically. `None` is returned when the dict would be empty so the column stores `NULL` rather than `{}`.

---

## Step 4 — `recompute_order_totals` update

**File:** `Delivery_app_BK/services/domain/order/recompute_order_totals.py`

Add the assignment of the new field:

```python
def recompute_order_totals(order: Order) -> None:
    """Recompute denormalized totals from in-memory order.items. Does NOT commit."""
    items = list(getattr(order, "items", None) or [])
    totals = calculate_item_totals(items)
    order.total_weight_g    = totals["total_weight"]
    order.total_volume_cm3  = totals["total_volume"]
    order.total_item_count  = totals["total_items"]
    order.item_type_counts  = totals["item_type_counts"]
```

This is the only place that writes `item_type_counts`. All four item-mutating commands already call `recompute_order_totals` before flushing, so no changes are needed in those commands.

---

## Why no changes are needed in the command layer

`recompute_order_totals` is called in the following call paths already:

| Command | Where `recompute_order_totals` is called |
|---------|------------------------------------------|
| `create_order.py` | line 206 — after all items are appended to the order |
| `create_item.py` | inside `for order in _unique_orders(touched_orders)` loop |
| `update_item.py` | inside `for order in _unique_orders(touched_orders)` loop |
| `delete_item.py` | inside `for order in _unique_orders(touched_orders)` loop |

All four paths reload `order.items` (via `db.session.expire(order, ['items'])` in `create_item.py`, or via the relationship being already in scope for the others) before calling `recompute_order_totals`. The new field will be computed and written as a side effect of the existing calls.

---

## Step 5 — Tests

### 5.1  Unit test for `calculate_item_totals`

**File:** `tests/unit/services/queries/utils/test_metrics.py`
(create or add to existing file)

```python
from types import SimpleNamespace
from Delivery_app_BK.services.queries.utils.metrics import calculate_item_totals


def _make_item(item_type, quantity, weight=0, h=0, w=0, d=0):
    return SimpleNamespace(
        item_type=item_type,
        quantity=quantity,
        weight=weight,
        dimension_height=h,
        dimension_width=w,
        dimension_depth=d,
    )


def test_item_type_counts_basic():
    items = [
        _make_item("Sofa", 1),
        _make_item("Dining chair", 4),
        _make_item("Dining chair", 2),
    ]
    result = calculate_item_totals(items)
    assert result["item_type_counts"] == {"Sofa": 1, "Dining chair": 6}


def test_item_type_counts_excludes_zero_quantity():
    items = [_make_item("Sofa", 0)]
    result = calculate_item_totals(items)
    assert result["item_type_counts"] is None


def test_item_type_counts_none_when_no_items():
    result = calculate_item_totals([])
    assert result["item_type_counts"] is None


def test_item_type_counts_skips_none_type():
    items = [
        _make_item(None, 2),
        _make_item("Sofa", 1),
    ]
    result = calculate_item_totals(items)
    assert result["item_type_counts"] == {"Sofa": 1}
```

### 5.2  Unit test for `recompute_order_totals`

**File:** `tests/unit/services/domain/order/test_recompute_order_totals.py`

```python
from types import SimpleNamespace
from unittest.mock import patch
from Delivery_app_BK.services.domain.order.recompute_order_totals import recompute_order_totals


def _make_order(items):
    return SimpleNamespace(
        items=items,
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        item_type_counts=None,
    )


def _make_item(item_type, quantity):
    return SimpleNamespace(
        item_type=item_type,
        quantity=quantity,
        weight=0,
        dimension_height=0,
        dimension_width=0,
        dimension_depth=0,
    )


def test_recompute_sets_item_type_counts():
    order = _make_order([_make_item("Sofa", 2), _make_item("Lamp", 1)])
    recompute_order_totals(order)
    assert order.item_type_counts == {"Sofa": 2, "Lamp": 1}


def test_recompute_sets_none_when_no_items():
    order = _make_order([])
    recompute_order_totals(order)
    assert order.item_type_counts is None
```

---

## Implementation Order

1. Add column to model (`order.py`) — 1 line
2. Generate and verify Alembic migration
3. Extend `calculate_item_totals` in `metrics.py`
4. Update `recompute_order_totals` in `recompute_order_totals.py`
5. Run existing tests — no existing tests should break
6. Add new tests from Section 5

---

## What is NOT in scope

- Backfilling historical rows — out of scope for this change
- Exposing `item_type_counts` through a serializer or API response — that is a separate frontend-facing change
- Indexing the JSONB column — not needed until a query pattern emerges that filters or aggregates by type
