# RoutePlan & RouteGroup item_type_counts — Implementation Plan

**Date:** 2026-04-01
**Depends on:** `ORDER_ITEM_TYPE_COUNTS_IMPLEMENTATION_2026-04-01.md` — the `Order.item_type_counts`
column must exist and be populated before the aggregation queries in this plan will return meaningful data.
**Column name:** `item_type_counts`
**Tables:** `route_plan`, `route_group`
**Type:** `JSONB` — `dict[str, int]`, same contract as `Order.item_type_counts`

---

## Purpose

Extend the `item_type_counts` snapshot upward from `Order` to `RouteGroup` and `RoutePlan`,
so that plan-level previews and statistics can show item type breakdowns without loading
orders or items.

---

## Important: call-path difference between plan and route group

`recompute_plan_totals` is called from all item-mutation commands (create, update, delete item)
via `_recompute_affected_plans`. So `RoutePlan.item_type_counts` stays current any time an item changes.

`recompute_route_group_totals` is **not** called from item-mutation commands. It is called when
the plan structure changes (plan created, order assigned to a plan, route groups materialized from zones).
This matches the existing behaviour for all other RouteGroup totals — they are not live-updated on
item changes either. `RouteGroup.item_type_counts` will therefore be consistent with the rest of the
`total_*` columns on that model.

---

## Files to Modify

| File | Change |
|------|--------|
| `models/tables/route_operations/route_plan/route_plan.py` | Add column |
| `models/tables/route_operations/route_plan/route_group.py` | Add column |
| `alembic/versions/<new>.py` | Migration (both tables, one revision) |
| `services/domain/route_operations/plan/recompute_plan_totals.py` | Aggregate from `Order.item_type_counts` |
| `services/domain/route_operations/plan/recompute_route_group_totals.py` | Aggregate per group from `Order.item_type_counts` |
| `services/commands/route_plan/create_serializers.py` | `serialize_created_route_group`, `serialize_created_route_plan` |
| `services/queries/route_plan/serialize_plan.py` | `serialize_plans` + `_serialize_route_group_summary` |
| `services/queries/route_plan/plan_types/serialize_route_group.py` | `_serialize_route_group_item` |
| `services/queries/route_plan/route_groups/get_route_group.py` | `_serialize_route_group_detail` |
| `services/queries/route_plan/route_groups/list_route_groups.py` | `_serialize_route_group` |

---

## Step 1 — Column definitions

### `route_plan.py`

Add after `total_orders`:

```python
item_type_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
```

Add the missing `JSON` import if not already present:
```python
from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, text, JSON
from sqlalchemy.dialects.postgresql import JSONB
```

### `route_group.py`

Add after `order_state_counts`:

```python
item_type_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
```

Same JSONB import pattern — both models already import `JSONB` and `JSON`.

---

## Step 2 — Alembic migration

One revision covers both tables:

```bash
.venv/bin/alembic revision --autogenerate -m "add item_type_counts to route_plan and route_group"
```

Verify the generated file adds exactly:

```python
op.add_column(
    "route_plan",
    sa.Column("item_type_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
)
op.add_column(
    "route_group",
    sa.Column("item_type_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
)
```

No backfill at migration time. Existing rows default to `NULL`.

---

## Step 3 — `recompute_plan_totals`

**File:** `services/domain/route_operations/plan/recompute_plan_totals.py`

Add one query after the existing aggregate. The function already issues a DB query; autoflush
ensures any in-session order changes are written before this query executes.

```python
def recompute_plan_totals(plan: "RoutePlan") -> None:
    """Aggregate Order denormalized totals into plan columns. No commit issued."""
    if plan is None or plan.id is None:
        return

    result = db.session.query(
        func.sum(Order.total_weight_g),
        func.sum(Order.total_volume_cm3),
        func.sum(Order.total_item_count),
        func.count(Order.id),
    ).filter(Order.route_plan_id == plan.id).one()

    plan.total_weight_g   = float(result[0] or 0)
    plan.total_volume_cm3 = float(result[1] or 0)
    plan.total_item_count = int(result[2] or 0)
    plan.total_orders     = int(result[3] or 0)

    # Merge per-order item_type_counts into a plan-level snapshot.
    type_counts_rows = (
        db.session.query(Order.item_type_counts)
        .filter(
            Order.route_plan_id == plan.id,
            Order.item_type_counts.isnot(None),
        )
        .all()
    )
    merged: dict[str, int] = {}
    for (counts,) in type_counts_rows:
        if counts:
            for k, v in counts.items():
                merged[k] = merged.get(k, 0) + v
    plan.item_type_counts = {k: v for k, v in merged.items() if v >= 1} or None

    logger.debug(
        "recompute_plan_totals plan_id=%s weight=%s volume=%s items=%s orders=%s",
        plan.id,
        plan.total_weight_g,
        plan.total_volume_cm3,
        plan.total_item_count,
        plan.total_orders,
    )
```

---

## Step 4 — `recompute_route_group_totals`

**File:** `services/domain/route_operations/plan/recompute_route_group_totals.py`

The function uses two paths (zone-backed vs no-zone). Extend each path to also collect
`item_type_counts` per group, then assign after the loop.

```python
def recompute_route_group_totals(plan) -> None:
    if plan is None or getattr(plan, "id", None) is None:
        return

    all_groups = (
        db.session.query(RouteGroup)
        .filter(RouteGroup.route_plan_id == plan.id)
        .all()
    )
    if not all_groups:
        return

    # ── Path 1: zone-backed groups ──────────────────────────────────────────
    zone_groups = [g for g in all_groups if g.zone_id is not None]
    if zone_groups:
        zone_ids = [g.zone_id for g in zone_groups]

        orders_per_zone = {
            zone_id: count
            for zone_id, count in (
                db.session.query(OrderZoneAssignment.zone_id, func.count(OrderZoneAssignment.id))
                .join(Order, Order.id == OrderZoneAssignment.order_id)
                .filter(
                    Order.route_plan_id == plan.id,
                    Order.team_id == plan.team_id,
                    OrderZoneAssignment.team_id == plan.team_id,
                    OrderZoneAssignment.is_unassigned.is_(False),
                    OrderZoneAssignment.zone_id.in_(zone_ids),
                )
                .group_by(OrderZoneAssignment.zone_id)
                .all()
            )
        }

        # Collect item_type_counts for zone-backed orders, keyed by zone_id.
        type_counts_per_zone: dict[int, dict[str, int]] = {zid: {} for zid in zone_ids}
        zone_order_rows = (
            db.session.query(OrderZoneAssignment.zone_id, Order.item_type_counts)
            .join(Order, Order.id == OrderZoneAssignment.order_id)
            .filter(
                Order.route_plan_id == plan.id,
                Order.team_id == plan.team_id,
                OrderZoneAssignment.team_id == plan.team_id,
                OrderZoneAssignment.is_unassigned.is_(False),
                OrderZoneAssignment.zone_id.in_(zone_ids),
                Order.item_type_counts.isnot(None),
            )
            .all()
        )
        for zone_id, counts in zone_order_rows:
            if counts:
                bucket = type_counts_per_zone[zone_id]
                for k, v in counts.items():
                    bucket[k] = bucket.get(k, 0) + v

        for group in zone_groups:
            group.total_orders = int(orders_per_zone.get(group.zone_id, 0))
            raw = type_counts_per_zone.get(group.zone_id, {})
            group.item_type_counts = {k: v for k, v in raw.items() if v >= 1} or None

    # ── Path 2: No-Zone bucket(s) ───────────────────────────────────────────
    no_zone_groups = [g for g in all_groups if g.zone_id is None]
    for group in no_zone_groups:
        count = (
            db.session.query(func.count(Order.id))
            .filter(
                Order.route_plan_id == plan.id,
                Order.route_group_id == group.id,
                Order.team_id == plan.team_id,
            )
            .scalar()
        ) or 0
        group.total_orders = int(count)

        type_counts_rows = (
            db.session.query(Order.item_type_counts)
            .filter(
                Order.route_plan_id == plan.id,
                Order.route_group_id == group.id,
                Order.team_id == plan.team_id,
                Order.item_type_counts.isnot(None),
            )
            .all()
        )
        merged: dict[str, int] = {}
        for (counts,) in type_counts_rows:
            if counts:
                for k, v in counts.items():
                    merged[k] = merged.get(k, 0) + v
        group.item_type_counts = {k: v for k, v in merged.items() if v >= 1} or None
```

---

## Step 5 — Serializers

### 5.1  `services/commands/route_plan/create_serializers.py`

**`serialize_created_route_group`** — add one field:

```python
def serialize_created_route_group(instance: RouteGroup) -> dict:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "route_plan_id": instance.route_plan_id,
        "state_id": instance.state_id,
        "total_weight_g": instance.total_weight_g,
        "total_volume_cm3": instance.total_volume_cm3,
        "total_item_count": instance.total_item_count,
        "total_orders": instance.total_orders,
        "order_state_counts": instance.order_state_counts,
        "item_type_counts": instance.item_type_counts,   # ← add
    }
```

**`serialize_created_route_plan`** — add one field. The function currently calls
`calculate_plan_metrics(instance)` which returns the live metric dict. Add `item_type_counts`
from the stored column alongside it:

```python
def serialize_created_route_plan(instance: RoutePlan) -> dict:
    serialized = {
        "id": instance.id,
        "client_id": instance.client_id,
        "label": instance.label,
        "date_strategy": instance.date_strategy,
        "start_date": _to_iso(instance.start_date),
        "end_date": _to_iso(instance.end_date),
        "created_at": _to_iso(instance.created_at),
        "updated_at": _to_iso(instance.updated_at),
        "state_id": instance.state_id,
        "item_type_counts": instance.item_type_counts,   # ← add
    }
    serialized.update(calculate_plan_metrics(instance))
    return serialized
```

### 5.2  `services/queries/route_plan/serialize_plan.py`

**`_serialize_route_group_summary`** — add `item_type_counts`:

```python
def _serialize_route_group_summary(route_group) -> dict:
    state = getattr(route_group, "state", None)
    snapshot_name = route_group_snapshot_name(
        getattr(route_group, "zone_geometry_snapshot", None)
    )
    return {
        "id": route_group.id,
        "name": snapshot_name,
        "zone_id": getattr(route_group, "zone_id", None),
        "total_orders": getattr(route_group, "total_orders", None),
        "item_type_counts": getattr(route_group, "item_type_counts", None),   # ← add
        "state": (
            {
                "id": state.id,
                "name": getattr(state, "name", None),
            }
            if state is not None
            else None
        ),
    }
```

**`serialize_plans`** — add `item_type_counts` alongside the existing stored totals block.
The `if instance.total_orders is not None` block already writes the stored columns;
add `item_type_counts` to the same dict update:

```python
if instance.total_orders is not None:
    unpacked.update({
        "total_weight": instance.total_weight_g,
        "total_volume": instance.total_volume_cm3,
        "total_items": instance.total_item_count,
        "total_orders": instance.total_orders,
        "item_type_counts": instance.item_type_counts,   # ← add
    })
```

### 5.3  `services/queries/route_plan/plan_types/serialize_route_group.py`

**`_serialize_route_group_item`** — add `item_type_counts`:

```python
def _serialize_route_group_item(instance: RouteGroup) -> dict:
    state = getattr(instance, "state", None)
    raw_snapshot = getattr(instance, "zone_geometry_snapshot", None)
    zone_snapshot = normalize_route_group_zone_snapshot(raw_snapshot)
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "zone_id": getattr(instance, "zone_id", None),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(instance, "template_snapshot", None),
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        "route_plan_id": instance.route_plan_id,
        "state_id": state.id if state is not None else None,
        "total_orders": instance.total_orders,
        "total_item_count": instance.total_item_count,
        "total_volume_cm3": instance.total_volume_cm3,
        "total_weight_grams": instance.total_weight_g,
        "order_state_counts": instance.order_state_counts,
        "item_type_counts": instance.item_type_counts,   # ← add
    }
```

### 5.4  `services/queries/route_plan/route_groups/get_route_group.py`

**`_serialize_route_group_detail`** — add `item_type_counts`:

```python
def _serialize_route_group_detail(route_group: RouteGroup) -> dict:
    ...
    return {
        "id": route_group.id,
        "client_id": route_group.client_id,
        "route_plan_id": route_group.route_plan_id,
        "zone_id": getattr(route_group, "zone_id", None),
        "is_system_default_bucket": getattr(route_group, "is_system_default_bucket", False),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(route_group, "template_snapshot", None),
        "updated_at": (
            route_group.updated_at.isoformat() if route_group.updated_at else None
        ),
        "state": (
            {"id": state.id, "name": state.name} if state is not None else None
        ),
        "total_orders": route_group.total_orders,
        "item_type_counts": route_group.item_type_counts,   # ← add
        "zone": (
            {
                "id": zone.id,
                "name": zone.name,
                "city_key": zone.city_key,
                "geometry": zone.geometry,
            }
            if zone is not None
            else None
        ),
    }
```

### 5.5  `services/queries/route_plan/route_groups/list_route_groups.py`

**`_serialize_route_group`** — add `item_type_counts`:

```python
def _serialize_route_group(route_group) -> dict:
    ...
    return {
        "id": route_group.id,
        "client_id": route_group.client_id,
        "zone_id": getattr(route_group, "zone_id", None),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(route_group, "template_snapshot", None),
        "updated_at": route_group.updated_at.isoformat() if route_group.updated_at else None,
        "route_plan_id": route_group.route_plan_id,
        "state": {
            "id": state.id,
            "name": state.name,
        }
        if state is not None
        else None,
        "total_orders": route_group.total_orders,
        "item_type_counts": route_group.item_type_counts,   # ← add
        "zone": {
            "id": zone.id,
            "name": zone.name,
            "city_key": zone.city_key,
            "geometry": zone.geometry,
        }
        if zone is not None
        else None,
        "active_route_solution": _serialize_selected_route_solution(route_group),
    }
```

---

## Step 6 — Tests

### 6.1  `recompute_plan_totals`

**File:** `tests/unit/services/domain/route_operations/plan/test_recompute_plan_totals.py`

```python
from unittest.mock import MagicMock, patch
from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import (
    recompute_plan_totals,
)


def _make_plan(plan_id=1):
    plan = MagicMock()
    plan.id = plan_id
    plan.total_weight_g = None
    plan.total_volume_cm3 = None
    plan.total_item_count = None
    plan.total_orders = None
    plan.item_type_counts = None
    return plan


def test_item_type_counts_merged_across_orders(monkeypatch):
    plan = _make_plan()

    # First query returns aggregate scalars
    aggregate_result = MagicMock()
    aggregate_result.__getitem__ = lambda self, i: [0, 0, 0, 2][i]

    # Second query returns per-order item_type_counts
    type_rows = [
        ({"Sofa": 1, "Dining chair": 4},),
        ({"Dining chair": 2, "Lamp": 1},),
    ]

    call_count = [0]
    mock_query = MagicMock()

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        m = MagicMock()
        if call_count[0] == 1:
            m.filter.return_value.one.return_value = aggregate_result
        else:
            m.filter.return_value.all.return_value = type_rows
        return m

    monkeypatch.setattr(
        "Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals.db.session.query",
        side_effect,
    )

    recompute_plan_totals(plan)

    assert plan.item_type_counts == {"Sofa": 1, "Dining chair": 6, "Lamp": 1}


def test_item_type_counts_none_when_no_orders(monkeypatch):
    plan = _make_plan()

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        m = MagicMock()
        if call_count[0] == 1:
            agg = MagicMock()
            agg.__getitem__ = lambda self, i: [None, None, None, 0][i]
            m.filter.return_value.one.return_value = agg
        else:
            m.filter.return_value.all.return_value = []
        return m

    monkeypatch.setattr(
        "Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals.db.session.query",
        side_effect,
    )

    recompute_plan_totals(plan)
    assert plan.item_type_counts is None


def test_skips_none_plan():
    # Must not raise
    recompute_plan_totals(None)
```

### 6.2  `recompute_route_group_totals`

The existing test file (if any) for this function should be extended. At minimum, add a test
that a no-zone group gets `item_type_counts` merged from its orders:

```python
def test_no_zone_group_item_type_counts(monkeypatch):
    """No-zone bucket aggregates item_type_counts from orders by route_group_id."""
    # Structure: one plan, one no-zone group, two orders
    # Query 1: all_groups → [group]
    # Query 2: count orders → 2
    # Query 3: item_type_counts rows → [{"Sofa": 1}, {"Sofa": 1, "Lamp": 2}]
    # Expected result: group.item_type_counts == {"Sofa": 2, "Lamp": 2}
    ...
```

Full mock wiring follows the same pattern as `test_recompute_plan_totals` above — query
call ordering must match the function's execution sequence.

---

## Implementation Order

1. Add columns to `route_plan.py` and `route_group.py` — 1 line each
2. Generate and verify Alembic migration
3. Extend `recompute_plan_totals` — add one query block after the existing aggregate
4. Extend `recompute_route_group_totals` — add `item_type_counts` to both zone and no-zone paths
5. Update all five serializer locations — one field addition each
6. Run existing test suite — no existing tests should break
7. Add new tests from Step 6

---

## What is NOT in scope

- Backfilling existing rows — the column starts as `NULL` on all existing plans and groups
- Indexing — not needed until a filter/aggregate query pattern emerges
- Surfacing `item_type_counts` on the frontend — that is a separate change
