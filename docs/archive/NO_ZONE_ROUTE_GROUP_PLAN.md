# No-Zone Route Group — Implementation Plan

Created: 2026-03-28
Status: Ready for implementation
Scope: Backend only

Read before starting:
- `Delivery_app_BK/services/commands/route_plan/create_plan.py` — plan creation command
- `Delivery_app_BK/services/requests/route_plan/plan/create_plan.py` — request schema
- `Delivery_app_BK/services/queries/order/list_orders.py` — order filtering (has the blocking bug)
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_group.py` — RouteGroup model
- `docs/under_development/ZONES_ROUTE_PLAN_INTEGRATION_GAPS.md` — GAP 1 (zone_ids on create plan)
  This plan integrates with and partially supersedes GAP 1's "Case B: no zone_ids → create nothing"

---

## Purpose

Every route plan always contains one **no-zone RouteGroup** — a catch-all partition that serves two roles:

1. **Onboarding bucket** — for teams that have not configured zones yet, the no-zone group
   is the only group. They can configure the RouteSolution via `route_group_defaults` in the
   create plan request and immediately start adding orders without any zone setup.

2. **Unassigned bucket** — for teams using zones, orders that cannot be spatially assigned to
   any zone (no zone coverage for their location, or `is_unassigned = True`) flow into this group.
   They remain visible and manageable inside the plan rather than being orphaned.

Without this group, the system blocks inexperienced users from using route directions
(`directions/orchestrator.py`) and route optimization because the RouteSolution created for
zone-specific groups lacks `set_start_time` and `start_location` until the user manually configures
them. The no-zone group's RouteSolution is pre-filled from request defaults, giving users an
immediate working route to interact with.

---

## Invariants

- Every plan has **exactly one** no-zone RouteGroup (`zone_id = NULL`)
- The no-zone group is always created at plan creation — it cannot be materialized separately
- The no-zone group **cannot be deleted** via the delete_route_group endpoint
- Zone-specific groups (from `zone_ids`) are created in addition to, not instead of, the no-zone group
- The no-zone group owns orders whose zone assignment is unresolved for this plan

---

## Changes Required

### 1 — Migration: partial unique index on route_group

**Priority: must run before any other change**

The existing `uq_route_group_team_plan_zone` unique constraint is `(team_id, route_plan_id, zone_id)`.
In PostgreSQL, `NULL` values are not considered equal in unique constraints — meaning two `NULL`
zone_id groups for the same plan are currently allowed by the DB. We need to prevent this.

**New migration:** add a partial unique index:

```sql
CREATE UNIQUE INDEX uq_route_group_unassigned_bucket_per_plan
ON route_group (team_id, route_plan_id)
WHERE zone_id IS NULL;
```

In Alembic:
```python
from alembic import op

def upgrade():
    op.create_index(
        "uq_route_group_unassigned_bucket_per_plan",
        "route_group",
        ["team_id", "route_plan_id"],
        unique=True,
        postgresql_where="zone_id IS NULL",
    )

def downgrade():
    op.drop_index(
        "uq_route_group_unassigned_bucket_per_plan",
        table_name="route_group",
    )
```

---

### 2 — `create_plan.py` command: always create the no-zone group

**File:** `Delivery_app_BK/services/commands/route_plan/create_plan.py`

The existing `_build_route_group_instances` function already creates a RouteGroup + RouteSolution
and pre-fills the solution from `route_group_defaults.route_solution`. This mechanism is correct
and must be kept. The change is to:

1. **Add `name` reading from defaults.** Currently `_build_route_group_instances` does not set
   `name` on the RouteGroup. Add:
   ```python
   name = defaults.get("name") or "Unassigned"
   ```
   Set this as the `name` field on the `RouteGroup` instance.

2. **Always call `_build_route_group_instances`.** The no-zone group is unconditionally created
   for every plan. This is the same as current behavior, but now with `name` populated.

3. **Zone-specific groups (from GAP 1 plan)**: if `zone_ids` are in the payload, create
   additional RouteGroups + RouteSolutions from zone templates. These are separate from the
   no-zone group. See `ZONES_ROUTE_PLAN_INTEGRATION_GAPS.md` GAP 1 for that logic.

**Summary of `_apply` loop after this change:**
```
for each plan in create_items:
    → create RoutePlan
    → create no-zone RouteGroup + RouteSolution  (always, from route_group_defaults)
    → if zone_ids in payload:
          create one RouteGroup + RouteSolution per zone_id  (from zone templates)
    → link order_ids to plan
    → commit
```

The `_build_route_group_instances` function signature and internals do not change, only the `name`
field is added to the created `RouteGroup`.

---

### 3 — `create_plan.py` request: allow `name` in `route_group_defaults`

**File:** `Delivery_app_BK/services/requests/route_plan/plan/create_plan.py`

No schema change is needed — `route_group_defaults` is currently validated as a free dict with
`_normalize_route_group_defaults`. The `name` key passes through today.

Verify this is still the case after any refactor. If a strict field-level validator is added to
`route_group_defaults` in the future, `name` must be listed as an allowed key.

No action required unless the schema is tightened.

---

### 4 — `list_orders.py`: fix the no-zone group order filter

**File:** `Delivery_app_BK/services/queries/order/list_orders.py`

**Current behavior (lines 33–48):**
```python
if route_group_id is not None:
    route_group = db.session.get(RouteGroup, route_group_id)
    if (
        route_group is None
        or (effective_route_plan_id is not None and route_group.route_plan_id != effective_route_plan_id)
        or route_group.zone_id is None          # <-- blocks ALL no-zone groups
    ):
        base_query = base_query.filter(false())
    else:
        base_query = base_query.join(
            OrderZoneAssignment, OrderZoneAssignment.order_id == Order.id
        ).filter(
            OrderZoneAssignment.zone_id == route_group.zone_id,
            OrderZoneAssignment.is_unassigned.is_(False),
        )
```

The `or route_group.zone_id is None` guard was written before the no-zone group concept existed.
It must be replaced with a proper branch.

**New behavior:**
```python
if route_group_id is not None:
    route_group = db.session.get(RouteGroup, route_group_id)

    # Guard: group must exist and belong to this plan
    if route_group is None or route_group.team_id != ctx.team_id:
        base_query = base_query.filter(false())
    elif effective_route_plan_id is not None and route_group.route_plan_id != effective_route_plan_id:
        base_query = base_query.filter(false())

    elif route_group.zone_id is None:
        # No-zone group: return orders that have no successful zone assignment
        # (unassigned = True, or no assignment record at all)
        base_query = (
            base_query
            .outerjoin(
                OrderZoneAssignment,
                OrderZoneAssignment.order_id == Order.id,
            )
            .filter(
                (OrderZoneAssignment.id.is_(None))
                | (OrderZoneAssignment.is_unassigned.is_(True))
            )
        )
    else:
        # Zone-specific group: return orders assigned to this zone
        base_query = base_query.join(
            OrderZoneAssignment, OrderZoneAssignment.order_id == Order.id
        ).filter(
            OrderZoneAssignment.zone_id == route_group.zone_id,
            OrderZoneAssignment.is_unassigned.is_(False),
        )
```

**Logic for the no-zone branch:**
- `LEFT OUTER JOIN` on `OrderZoneAssignment`
- Include orders where the join produces no row (`assignment.id IS NULL`) — order has never been zone-assigned
- Include orders where `is_unassigned = True` — assignment was attempted but could not resolve
- Exclude orders that have a successful zone assignment (`is_unassigned = False`) — those belong to a zone group

---

### 5 — `delete_route_group.py`: guard against deleting the no-zone group

**File:** `Delivery_app_BK/services/commands/route_plan/delete_route_group.py`

Add a check before the execution guard:

```python
if route_group.zone_id is None:
    raise ValidationFailed(
        "The unassigned bucket route group cannot be deleted. "
        "It is a system-managed group present on every plan."
    )
```

Place this after the team ownership check, before the `actual_start_time` execution guard.

---

### 6 — `total_orders` for the no-zone group at plan creation

**File:** `Delivery_app_BK/services/commands/route_plan/create_plan.py`

After `db.session.flush()` and before `db.session.commit()`, compute `total_orders` for the
no-zone group. The count is: orders being linked to this plan (`order_ids`) whose zone assignment
is unresolved or absent.

```python
if order_ids and no_zone_route_group is not None:
    from Delivery_app_BK.models import OrderZoneAssignment
    from sqlalchemy import func, or_, outerjoin

    unassigned_count = (
        db.session.query(func.count(Order.id))
        .outerjoin(
            OrderZoneAssignment,
            OrderZoneAssignment.order_id == Order.id,
        )
        .filter(
            Order.id.in_(order_ids),
            Order.team_id == ctx.team_id,
            or_(
                OrderZoneAssignment.id.is_(None),
                OrderZoneAssignment.is_unassigned.is_(True),
            ),
        )
        .scalar()
    )
    no_zone_route_group.total_orders = unassigned_count or 0
```

If no `order_ids` are passed at plan creation, `total_orders` defaults to `0` — correct, since
orders are added after creation.

Also update `recompute_route_group_totals` (from the GAP 4 plan in `ZONES_ROUTE_PLAN_INTEGRATION_GAPS.md`)
to handle the no-zone group using the same LEFT JOIN pattern as `list_orders` change above.

---

### 7 — Response shape

**File:** `Delivery_app_BK/services/commands/route_plan/create_plan.py`

The existing bundle key `"route_group"` continues to carry the no-zone group — preserving
backward compatibility with any existing frontend consumer:

```python
bundle = {
    "delivery_plan": serialize_created_route_plan(route_plan_instance),
    "route_group": serialize_created_route_group(no_zone_route_group),
}
if zone_route_groups:
    bundle["route_groups"] = [
        serialize_created_route_group(rg) for rg in zone_route_groups
    ]
```

- `route_group` (singular) — always present, always the no-zone group
- `route_groups` (plural) — present only when `zone_ids` were provided, contains zone-specific groups

---

## Implementation Order

1. Write and apply the **migration** (partial unique index) — must be first
2. Update `_build_route_group_instances` to set `name` from defaults — trivial, do alongside migration
3. Update `list_orders.py` — the LEFT JOIN branch for no-zone group
4. Update `delete_route_group.py` — add the no-zone group guard
5. Add `total_orders` computation for the no-zone group in `create_plan`
6. Integrate zone_ids path (GAP 1) — zone groups created in addition to the no-zone group
7. Write tests

---

## Testing Requirements

| Test file | What to test |
|---|---|
| `tests/unit/services/commands/plan/test_create_plan_no_zone_group.py` | Plan always has a no-zone group; name defaults to "Unassigned"; name overridden via `route_group_defaults.name`; RouteSolution pre-filled from `route_group_defaults.route_solution`; plan with zone_ids has no-zone group AND zone groups |
| `tests/unit/services/queries/order/test_list_orders_no_zone_group.py` | No-zone group returns unassigned orders; no-zone group does not return zone-assigned orders; zone group still works as before; group from different plan returns empty |
| `tests/unit/services/commands/plan/test_delete_route_group_guard.py` | Deleting no-zone group returns 400 with correct message; deleting zone group still works |

---

## What Does NOT Change

- `POST /route-plans/<id>/route-groups/materialize` — zone materialization is unchanged; it creates zone groups only, never touches the no-zone group
- `route_group_defaults.route_solution` fields (`set_start_time`, `start_location`, `end_location`, etc.) — these already work and continue to fill the no-zone group's RouteSolution
- Zone-specific RouteSolution settings — still filled from zone template config (see GAP 1 plan)
- All other plan, zone, and order endpoints — unchanged
