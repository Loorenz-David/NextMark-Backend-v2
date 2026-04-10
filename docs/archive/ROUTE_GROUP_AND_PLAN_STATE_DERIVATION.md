# Route Group & Route Plan State Derivation

**Date:** 2026-03-28
**Status:** Under Development

---

## Overview

Two derivation layers are currently unimplemented:

1. **Orders → Route Group state** — `route_group.state_id` is never assigned anywhere in the codebase
2. **Route Groups → Route Plan state** — no function derives plan state from its groups

The existing `maybe_auto_complete_plan` only handles auto-completion via route solution order counts (local delivery specific). The group-based plan state derivation is a separate, missing mechanism.

---

## Layer Placement

Both new domain functions belong in `services/domain/state_transitions/` — this is where `plan_state_engine.py` and `order_move_rules.py` already live. Pure functions, no I/O, no DB writes.

---

## Step 1 — Create `route_group_state_engine.py`

**File:** `Delivery_app_BK/services/domain/state_transitions/route_group_state_engine.py`

**Purpose:** Pure functions for deriving and safely setting route group state from its orders.

**OrderState → PlanState mapping** (for group derivation):

| All active orders in group | Derived group state |
|---|---|
| All `COMPLETED` | `PlanStateId.COMPLETED` |
| All `PROCESSING` | `PlanStateId.PROCESSING` |
| All `READY` | `PlanStateId.READY` |
| Any other / mixed / empty | `PlanStateId.OPEN` |

Cancelled orders (`OrderStateId.CANCELLED`) must be **excluded** from the derivation — a group with one active PROCESSING order and several CANCELLED orders should derive PROCESSING, not OPEN.

**Functions to implement:**

```python
def apply_route_group_state(route_group, state_id: int) -> bool:
    """Idempotent safe setter. Mirrors apply_plan_state. Returns True if changed."""
    if route_group.state_id == state_id:
        return False
    route_group.state_id = state_id
    return True


def derive_route_group_state(route_group) -> int:
    """
    Pure derivation from route_group.orders (lazy=selectin, already loaded).
    Excludes CANCELLED orders from the evaluation.
    Returns a PlanStateId integer.
    """
    active_orders = [o for o in route_group.orders if o.order_state_id != OrderStateId.CANCELLED]
    if not active_orders:
        return PlanStateId.OPEN

    state_ids = {o.order_state_id for o in active_orders}
    if state_ids == {OrderStateId.COMPLETED}:
        return PlanStateId.COMPLETED
    if state_ids == {OrderStateId.PROCESSING}:
        return PlanStateId.PROCESSING
    if state_ids == {OrderStateId.READY}:
        return PlanStateId.READY
    return PlanStateId.OPEN


def maybe_sync_route_group_state(route_group) -> bool:
    """Derives and applies route group state. Returns True if state changed."""
    derived = derive_route_group_state(route_group)
    return apply_route_group_state(route_group, derived)
```

**Imports needed:**
- `OrderStateId` from `services/domain/order/order_states.py`
- `PlanStateId` from `services/domain/route_operations/plan/plan_states.py`

---

## Step 2 — Extend `plan_state_engine.py`

**File:** `Delivery_app_BK/services/domain/state_transitions/plan_state_engine.py`

Add two functions at the bottom of the existing file:

```python
def derive_plan_state_from_groups(plan) -> int:
    """
    Pure derivation of plan state from its route groups.
    Matrix (strict all-must-match rule):
      - All groups COMPLETED  → PlanStateId.COMPLETED
      - All groups PROCESSING → PlanStateId.PROCESSING
      - All groups READY      → PlanStateId.READY
      - Empty / mixed / any OPEN → PlanStateId.OPEN
    """
    groups = [g for g in plan.route_groups if not getattr(g, "deleted_at", None)]
    if not groups:
        return PlanStateId.OPEN

    state_ids = {g.state_id for g in groups}
    if len(state_ids) == 1:
        sole = next(iter(state_ids))
        if sole in (PlanStateId.COMPLETED, PlanStateId.PROCESSING, PlanStateId.READY):
            return sole
    return PlanStateId.OPEN


def maybe_sync_plan_state_from_groups(plan) -> bool:
    """Derives plan state from route groups and applies it. Returns True if changed."""
    derived = derive_plan_state_from_groups(plan)
    return apply_plan_state(plan, derived)
```

`apply_plan_state` already exists in this file — reuse it directly.

---

## Step 3 — Wire into `update_order_route_plan.py`

There are **two call sites** in this file that need the new sync chain.

### Call site A — `_apply_move_state_heritage`

Add `affected_route_groups: list` as a new parameter (groups whose order composition changed — both source groups before the move and destination groups after). After the existing `maybe_auto_complete_plan` loop:

```python
def _apply_move_state_heritage(
    *,
    ctx,
    changed_orders,
    new_plan,
    plans_to_recompute,
    affected_route_groups,   # NEW parameter
    case_message,
) -> None:
    # ... existing logic unchanged ...

    # NEW: sync route group states then derive plan state
    for group in affected_route_groups:
        maybe_sync_route_group_state(group)

    for plan in plans_to_recompute.values():
        maybe_sync_plan_state_from_groups(plan)
```

To populate `affected_route_groups`, collect route groups from `changed_orders` at the call site in `apply_orders_route_plan_change`: capture `order.route_group` (source, before the move) and the destination group (if any). Deduplicate by id before passing.

### Call site B — `apply_orders_route_plan_unassign`

After the existing loop over `old_plans_by_id` (the block calling `recompute_plan_order_counts` + `maybe_auto_complete_plan`):

```python
for plan in old_plans_by_id.values():
    recompute_plan_totals(plan)
    recompute_route_group_totals(plan)
    recompute_plan_order_counts(plan)
    maybe_auto_complete_plan(plan)
    # NEW: sync route group and plan states
    for group in plan.route_groups:
        maybe_sync_route_group_state(group)
    maybe_sync_plan_state_from_groups(plan)
```

---

## Step 4 — Future hook location (out of scope, must be tracked)

When an **individual order state changes** (e.g., driver transitions an order to PROCESSING), the same two-layer sync must fire. Find the command(s) that transition order states and add:

```python
# After order.order_state_id is set:
if order.route_group_id:
    maybe_sync_route_group_state(order.route_group)
    maybe_sync_plan_state_from_groups(order.route_group.route_plan)
```

This is a separate task but must be done to keep group and plan states consistent outside of order-move flows.

---

## Files to Create or Modify

| Action | File |
|---|---|
| **Create** | `services/domain/state_transitions/route_group_state_engine.py` |
| **Modify** | `services/domain/state_transitions/plan_state_engine.py` — add `derive_plan_state_from_groups`, `maybe_sync_plan_state_from_groups` |
| **Modify** | `services/commands/order/update_order_route_plan.py` — wire both call sites |

---

## Invariants Copilot Must Preserve

1. **No flush/commit inside domain functions** — `apply_route_group_state`, `derive_route_group_state`, and the two new plan functions must be flush-free. Callers own the session boundary.
2. **Cancelled orders are excluded** from group state derivation — they must not pull a group back to OPEN.
3. **Empty groups evaluate to OPEN** — a group with no active orders is ground state.
4. **`apply_plan_state` is the only safe setter for plan state** — `maybe_sync_plan_state_from_groups` must call `apply_plan_state`, never assign `plan.state_id` directly.
5. **Coexistence with `maybe_auto_complete_plan`** — do not remove it. It handles a separate path (route solution based auto-completion for local delivery). Both run; group-based sync runs after it.
