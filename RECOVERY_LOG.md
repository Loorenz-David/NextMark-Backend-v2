# Backend Recovery Log — Post-Commit Breakage

## The Problem

A `git add . && git commit` was run from the monorepo root (`NextMark-app/`) while two VS Code windows were open with different in-progress states. The resulting commit (`93964aa — "finish app for deploying in ec2"`) produced a snapshot that mixed two divergent work streams:

- New AI operator phase code referencing modules/functions that had been renamed or deleted
- Old model relationships referencing table names that had changed
- New SQLAlchemy relationships added without the corresponding FK columns
- Blueprint import paths pointing to a folder structure that no longer exists

**The backend now starts cleanly after the fixes below. The frontend is not yet fixed.**

---

## Patterns of Breakage

These are the recurring failure modes. When you hit a new error, match it to one of these patterns first.

### Pattern A — `delivery_plan` → `route_plan` rename
The `DeliveryPlan` model and its DB table were renamed to `RoutePlan` / `route_plan`. Any reference to the old name is broken.

| Old | New |
|---|---|
| `DeliveryPlan` (class) | `RoutePlan` |
| `"DeliveryPlan"` (SQLAlchemy string ref) | `"RoutePlan"` |
| FK target `delivery_plan.id` | `route_plan.id` |
| `order.delivery_plan` (ORM relationship) | `order.route_plan` |
| `routers/api_v2/delivery_plan/` | `routers/api_v2/route_plan/` |
| `services/queries/plan/` | `services/queries/route_plan/` |
| `services/commands/plan/` | `services/commands/route_plan/` |

### Pattern B — Deleted functions still being imported
Functions were removed by the commit but their import statements remain in other files. Strategy: grep for the function name, find where it currently lives (or what it was renamed to), fix the import. Do not invent new implementations unless the function genuinely needs to be restored.

### Pattern C — New ORM relationships without FK columns
The commit added `relationship()` entries to models without adding the required `Column(ForeignKey(...))`. SQLAlchemy raises `NoForeignKeysError` at startup. Fix: remove the relationship if it was added incorrectly, or add the FK column + migration if it is genuinely needed.

### Pattern D — Blueprint variable name mismatches
Router files under `route_plan/` export differently named blueprint variables than what `__init__.py` expects. Fix with aliased imports: `from .route_plan.plan import route_plans_bp as plan_bp`.

### Pattern E — Wrong constructor field names
Dataclass/Pydantic constructors were called with old keyword argument names. Fix by matching to the current field names in the class definition.

---

## All Fixes Applied (in order)

### Fix 1 — `adjust_driver_route_dates_to_today.py`
**File:** `Delivery_app_BK/services/commands/drivers/adjust_driver_route_dates_to_today.py`
**Error:** `TypeError: RouteGroupSettingsRequest.__init__() got an unexpected keyword argument 'delivery_plan'`
**Pattern:** E
**Fix:** Renamed kwargs `delivery_plan=` → `route_plan=` and `local_delivery_plan=` → `route_group=` to match the current `RouteGroupSettingsRequest` dataclass.

---

### Fix 2 — `RoutePlan` model validator crash on backward date move
**File:** `Delivery_app_BK/models/tables/route_operations/route_plan/route_plan.py`
**Error:** `ValueError: end_date cannot be before start_date` when moving a plan to an earlier date.
**Root cause:** `validate_start_date` auto-sets `self.end_date` for single-day plans. This triggers `validate_end_date`, which compares the new end against `self.start_date` — but at that moment `self.start_date` is still the OLD (future) value. Result: false violation.
**Fix:** Changed the auto-set in `validate_start_date` to write directly to `self.__dict__["end_date"]`, bypassing the `validate_end_date` chain. The auto-set value is always valid by construction (end-of-day of the new start), so skipping the cross-field check here is safe.

---

### Fix 3 — `resolve_next_window_start` deleted from `time_window_policy.py`
**File:** `Delivery_app_BK/directions/services/time_window_policy.py`
**Error:** `ImportError: cannot import name 'resolve_next_window_start'`
**Pattern:** B
**Fix:** Restored the function. It returns the start of the earliest window whose start is after `arrival_time`, or `None` if arrival is already inside a window or past all windows. Built using the existing `_normalize_windows` and `_is_arrival_inside_any_window` helpers already in the file.

---

### Fix 4 — `ai/tools/plan_tools.py` — four broken imports
**File:** `Delivery_app_BK/ai/tools/plan_tools.py`
**Pattern:** A + B
**Fixes:**
- `optimize_local_delivery_plan` → `from route_optimization.orchestrator import optimize_route_plan as optimize_local_delivery_plan`
- `services.queries.plan.get_plan` → `services.queries.route_plan.get_plan`
- `services.queries.plan.list_delivery_plans` → `services.queries.route_plan.find_plans` (aliased; also fixed call signature from `fn(ctx)` to `fn(params, ctx)`)
- `services.commands.plan.create_plan` → `services.commands.route_plan.create_plan`

---

### Fix 5 — `ai/tools/order_tools.py` — wrong import path
**File:** `Delivery_app_BK/ai/tools/order_tools.py`
**Error:** `ModuleNotFoundError: No module named '...update_order_delivery_plan'`
**Pattern:** B
**Fix:** `update_orders_delivery_plan` → aliased from `apply_orders_route_plan_change` in `services/commands/order/update_order_route_plan.py`. Same signature `(ctx, order_ids, plan_id)`, same return shape.

---

### Fix 6 — `order_events.py` — two missing builder functions
**File:** `Delivery_app_BK/services/infra/events/builders/order/order_events.py`
**Error:** `ImportError: cannot import name 'build_delivery_rescheduled_event'`
**Pattern:** B
**Fix:** Restored both deleted functions:
- `build_delivery_rescheduled_event(order, *, old_plan_start, old_plan_end, new_plan_start, new_plan_end, reason)` → emits `OrderEvent.DELIVERY_RESCHEDULED`
- `build_route_plan_changed_event(order, old_plan_id, new_plan)` → emits `OrderEvent.DELIVERY_PLAN_CHANGED`

---

### Fix 7 — `sockets/contracts/realtime.py` — missing constant
**File:** `Delivery_app_BK/sockets/contracts/realtime.py`
**Error:** `ImportError: cannot import name 'BUSINESS_EVENT_ROUTE_PLAN_UPDATED'`
**Pattern:** B
**Fix:** Added `BUSINESS_EVENT_ROUTE_PLAN_UPDATED = "route_plan.updated"` following the existing naming convention in the file.

---

### Fix 8 — `routers/api_v2/__init__.py` — blueprint imports pointing to deleted folder
**File:** `Delivery_app_BK/routers/api_v2/__init__.py`
**Error:** `ModuleNotFoundError: No module named '...routers.api_v2.delivery_plan'`
**Pattern:** A + D
**Fix:** The `delivery_plan/` router folder no longer exists — it was renamed to `route_plan/`. Blueprint variable names also changed. Fixed with aliased imports:
```python
from .route_plan.local_delivery_plans import route_groups_bp as local_delivery_plans_bp
from .route_plan.plan import route_plans_bp as plan_bp
from .route_plan.plan_overviews import route_plan_overviews_bp as plan_overviews_bp
from .route_plan.route_operations import route_operations_bp
```

---

### Fix 9 — `models/tables/order/order.py` — broken ORM relationship (3 sub-fixes)
**File:** `Delivery_app_BK/models/tables/order/order.py`
**Pattern:** A + C

**9a — Class name:** `relationship("DeliveryPlan", ...)` → `relationship("RoutePlan", ...)`

**9b — FK column:** `ForeignKey("delivery_plan.id", ...)` → `ForeignKey("route_plan.id", ...)`. The DB table was renamed so the FK target must match.

**9c — Relationship name and back_populates:** `RoutePlan.orders` uses `back_populates="route_plan"`, so the `Order` side must be named `route_plan` (not `delivery_plan`). Renamed the relationship attribute and added `foreign_keys=[delivery_plan_id]`.

**Call site updated:** `create_order.py` line 153: `order_instance.delivery_plan = ...` → `order_instance.route_plan = ...`

---

### Fix 10 — `route_group.py` — spurious ORM relationship without FK
**File:** `Delivery_app_BK/models/tables/route_operations/route_plan/route_group.py`
**Error:** `NoForeignKeysError: Could not determine join condition between 'route_group' and 'order'`
**Pattern:** C
**Fix:** Removed `orders = relationship("Order", back_populates="route_group")`. There is no FK from `order` to `route_group` and none was ever added. Orders relate to route groups only through `RouteSolutionStop`, not via a direct FK.

**Secondary fix:** `route_group_state_engine.py` used `route_group.orders` as a fallback path. Changed to `getattr(route_group, "orders", None) or []` so it degrades gracefully instead of crashing. The primary path (denormalized `order_state_counts`) is unaffected.

---

## Current State

**Backend:** starts cleanly. All import errors and mapper configuration errors resolved.

**Frontend:** not touched. The same commit modified files across `Front_end/admin-app/`, `Front_end/driver-app/`, `Front_end/client-form-app/`, and `Front_end/tracking-order-app/`. Expect the same class of errors — renamed imports, deleted exports still referenced, type name mismatches. Start each app's dev server, collect the first error, trace the import chain, fix with the nearest real equivalent.

---

## How to Confirm a Fix is Correct

- **Backend:** `python run.py` reaches `Socket.IO initialized` with no traceback.
- **Frontend:** `npm run dev` or `vite build` completes with no unresolved import or TypeScript errors.
- One broken symbol = one fix. Do not refactor surrounding code.
