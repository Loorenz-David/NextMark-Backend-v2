# Route Naming Migration — Steps C and D Handoff

**Date:** 2026-03-26
**Repository:** Back_end
**Scope:** AI tool contract alignment (C) and legacy wrapper retirement (D)
**Author context:** Continuation of the route_plan / route_group naming migration. Steps A and B are already complete.

---

## Background

The backend renamed its core planning domain:

| Legacy name | Canonical name |
|---|---|
| `DeliveryPlan` | `RoutePlan` |
| `LocalDeliveryPlan` | `RouteGroup` |
| `delivery_plan_id` (payload key) | `route_plan_id` |
| `local_delivery_plan_id` (payload key) | `route_group_id` |
| `"delivery_plan.created/updated/deleted"` (socket event) | `"route_plan.created/updated/deleted"` |
| `"local_delivery_plan.updated"` (socket event) | `"route_group.updated"` |

The model layer is already canonical. Compatibility aliases are still present in many places to avoid breaking the frontend mid-migration. Steps C and D finish the backend side.

---

## Step C — AI Prompt and Tool Contract Alignment

The AI module (`Delivery_app_BK/ai/`) is the last backend subsystem still using legacy naming heavily. These changes are **mechanical substitutions** — there is no logic to redesign, only naming to correct.

---

### C.1 — Fix broken import in `tool_registry.py` and `plan_tools.py`

**Problem:** The import path `Delivery_app_BK.services.queries.plan.get_plan` does not exist. The module moved to `route_plan`.

**File:** `Delivery_app_BK/ai/tools/plan_tools.py`

Find and replace this import (near top of file):
```python
# BEFORE
from Delivery_app_BK.services.queries.plan.get_plan import get_plan as get_plan_service
```
```python
# AFTER
from Delivery_app_BK.services.queries.route_plan.get_route_plan import (
    get_route_plan as get_plan_service,
)
```

Also check `Delivery_app_BK/ai/tool_registry.py` for any similar broken import of `services.queries.plan.*` and apply the same fix.

---

### C.2 — Rename parameter in `optimize_plan_tool()`

**File:** `Delivery_app_BK/ai/tools/plan_tools.py`

Find `optimize_plan_tool`. The parameter is named `local_delivery_plan_id`. Rename it to `route_plan_id` everywhere inside the function.

```python
# BEFORE
def optimize_plan_tool(ctx: ServiceContext, local_delivery_plan_id: int) -> dict:
    ctx.incoming_data["local_delivery_plan_id"] = local_delivery_plan_id
    ...
```
```python
# AFTER
def optimize_plan_tool(ctx: ServiceContext, route_plan_id: int) -> dict:
    ctx.incoming_data["route_plan_id"] = route_plan_id
    ...
```

> **Important:** The downstream command reads from `ctx.incoming_data`. Confirm what key the optimize command reads. If it reads `"local_delivery_plan_id"`, add a compatibility alias:
> ```python
> ctx.incoming_data["route_plan_id"] = route_plan_id
> ctx.incoming_data["local_delivery_plan_id"] = route_plan_id  # compat until command updated
> ```

---

### C.3 — Fix column reference in `list_routes_tool()`

**File:** `Delivery_app_BK/ai/tools/plan_tools.py`

Find the filter inside `list_routes_tool` (approximately line 177):
```python
# BEFORE
query = query.filter(RouteSolution.local_delivery_plan_id == plan_id)
```
```python
# AFTER
query = query.filter(RouteSolution.route_group_id == plan_id)
```

The canonical column name on `RouteSolution` is `route_group_id`. The legacy name `local_delivery_plan_id` no longer exists on the model.

---

### C.4 — Fix `local_delivery_handler.py`

**File:** `Delivery_app_BK/ai/tools/plan_execution/local_delivery_handler.py`

Three things to fix:

**a) Relationship load:**
```python
# BEFORE
selectinload(RouteSolution.local_delivery_plan)
```
```python
# AFTER
selectinload(RouteSolution.route_group)
```

**b) Filter column:**
```python
# BEFORE
RouteSolution.local_delivery_plan_id == plan.id
```
```python
# AFTER
RouteSolution.route_group_id == plan.id
```

**c) Relationship access:**
```python
# BEFORE
"plan_label": route.local_delivery_plan.label if route.local_delivery_plan else plan.label
```
```python
# AFTER
"plan_label": route.route_group.label if route.route_group else plan.label
```

---

### C.5 — Update prompt documentation for `optimize_plan`

**File:** `Delivery_app_BK/ai/prompts/system_prompt.py`

Find the documentation block for `optimize_plan` (around line 113). Change the parameter name:
```python
# BEFORE
- optimize_plan: Run route optimization on a local delivery plan.
  Parameters: {{ "local_delivery_plan_id": <integer> }}
```
```python
# AFTER
- optimize_plan: Run route optimization on a route plan.
  Parameters: {{ "route_plan_id": <integer> }}
```

---

### C.6 — Update prompt documentation in `logistics_execute_prompt.py`

**File:** `Delivery_app_BK/ai/prompts/logistics_execute_prompt.py`

Two locations to update:

**a)** Find the `optimize_plan` tool documentation (around line 182):
```python
# BEFORE
- optimize_plan: ... Parameters: {{ "local_delivery_plan_id": <integer> }}
```
```python
# AFTER
- optimize_plan: ... Parameters: {{ "route_plan_id": <integer> }}
```

**b)** Find the `create_order` parameter list (around line 293). Change:
```python
# BEFORE
delivery_plan_id (integer): optional
```
```python
# AFTER
route_plan_id (integer): optional
# Keep delivery_plan_id as accepted alias only if the create_order service still reads it.
# The create_order service currently accepts both — document the canonical one.
```

---

### C.7 — Update `response_formatter.py` key lookups

**File:** `Delivery_app_BK/ai/response_formatter.py`

Find places that read `"delivery_plan"` / `"delivery_plans"` keys from API responses (around lines 145, 161). These should check canonical key first:

```python
# BEFORE (example)
plans = result.get("delivery_plans") or result.get("plans") or []
plan  = result.get("delivery_plan") or {}
```
```python
# AFTER
plans = result.get("route_plans") or result.get("delivery_plans") or result.get("plans") or []
plan  = result.get("route_plan") or result.get("delivery_plan") or {}
```

Also around line 255:
```python
# BEFORE
plan_id = params.get("plan_id") or params.get("delivery_plan_id")
```
```python
# AFTER
plan_id = params.get("plan_id") or params.get("route_plan_id") or params.get("delivery_plan_id")
```

---

### C.8 — Update `collection_presentation.py` field references

**File:** `Delivery_app_BK/ai/collection_presentation.py`

Find occurrences of `"delivery_plan_id"` (around lines 15, 57, 137–141) and add `"route_plan_id"` as the canonical primary check:

```python
# BEFORE
if "delivery_plan_id" not in focus:
    ...
if params.get("plan_id") is not None and "delivery_plan_id" not in focus:
    ...
```
```python
# AFTER
plan_id_key = "route_plan_id" if "route_plan_id" in focus else "delivery_plan_id"
if plan_id_key not in focus:
    ...
if params.get("plan_id") is not None and plan_id_key not in focus:
    ...
```

For inline field lists that include `"delivery_plan_id"` as a named field to extract, add `"route_plan_id"` before it:
```python
# BEFORE
"delivery_plan_id",
```
```python
# AFTER
"route_plan_id",
"delivery_plan_id",   # legacy alias — remove in Step D
```

---

### C.9 — Update `AI_OPERATOR.md`

**File:** `Delivery_app_BK/ai/AI_OPERATOR.md`

This is the authoritative architecture reference. Update the following sections:

**a) Registered Tools table** — for every tool row that mentions `local_delivery_plan_id` or `delivery_plan_id` as a parameter, change to `route_plan_id`.

**b) Domain model section** — any reference to `Order.delivery_plan_id` field should read `Order.delivery_plan_id` with a note: *(DB column name; canonical API key is `route_plan_id`)*.

**c) MUTABLE_FIELDS allowlist** — if `delivery_plan_id` appears as a mutable field description, note that the canonical key accepted by the API is `route_plan_id` (the service layer accepts both).

**d) State machine / command path references** — verify service import paths mentioned in the doc still exist. For any path containing `services/queries/plan/`, update to `services/queries/route_plan/`.

> Rule from `CLAUDE.md`: `AI_OPERATOR.md` must be updated after every build or modification in the `ai/` module. Do this last, after C.1–C.8 are implemented and tests pass.

---

### C — Verification

After all C changes, run:
```bash
python -m pytest tests/unit/ai/ -v
```

Fix any remaining import errors before proceeding to Step D.

Also run:
```bash
python -c "from Delivery_app_BK.ai.tool_registry import TOOLS; print('OK')"
```

This will catch any remaining broken import in the tool chain without needing a running server.

---

## Step D — Wrapper Retirement

**Do not start Step D until:**
1. All Step C changes are complete and tests pass.
2. Frontend admin app has switched all socket listeners from legacy to canonical event names.
3. Frontend admin app no longer sends `delivery_plan_id` or `local_delivery_plan_id` in request payloads.
4. `scripts/report_route_naming_legacy_refs.py` shows zero or near-zero remaining references.

---

### D.1 — Retire socket event name aliases

**File:** `Delivery_app_BK/sockets/contracts/realtime.py`

Give `BUSINESS_EVENT_ROUTE_GROUP_UPDATED` its own canonical value instead of aliasing to the legacy string:

```python
# BEFORE
BUSINESS_EVENT_LOCAL_DELIVERY_PLAN_UPDATED = "local_delivery_plan.updated"
BUSINESS_EVENT_ROUTE_GROUP_UPDATED = BUSINESS_EVENT_LOCAL_DELIVERY_PLAN_UPDATED
```
```python
# AFTER
BUSINESS_EVENT_ROUTE_GROUP_UPDATED = "route_group.updated"
# Legacy constant kept only for code reading old constants; do not use in new emitters.
BUSINESS_EVENT_LOCAL_DELIVERY_PLAN_UPDATED = "local_delivery_plan.updated"  # DEPRECATED
```

Then update `DELIVERY_PLANNING_NOTIFICATION_EVENT_NAMES` in `notifications.py` to remove the four legacy entries:
```python
# Remove these four lines:
LEGACY_ROUTE_PLAN_EVENT_CREATED,       # "delivery_plan.created"
LEGACY_ROUTE_PLAN_EVENT_UPDATED,       # "delivery_plan.updated"
LEGACY_ROUTE_PLAN_EVENT_DELETED,       # "delivery_plan.deleted"
LEGACY_ROUTE_GROUP_EVENT_UPDATED,      # "local_delivery_plan.updated"
```

Only do this once you have confirmed the frontend is not emitting or relying on these event names.

---

### D.2 — Retire legacy payload keys in socket emitters

**Files to audit (grep for legacy keys in each):**
- `Delivery_app_BK/sockets/emitters/local_delivery_plan_events.py`
- `Delivery_app_BK/sockets/emitters/route_solution_events.py`
- `Delivery_app_BK/sockets/emitters/delivery_plan_events.py`

In each file, remove the legacy mirror keys from the payload dict once the frontend no longer reads them:

**`delivery_plan_events.py` — when ready:**
```python
# Remove this line from the payload:
"delivery_plan_id": plan.id,   # DEPRECATED legacy key
```

**`local_delivery_plan_events.py` — when ready:**
```python
# Remove these lines from the payload:
"local_delivery_plan_id": route_group_id,   # DEPRECATED legacy key
"delivery_plan_id": route_plan_id,          # DEPRECATED legacy key
```

**`route_solution_events.py` `_plan_id_aliases()` helper — when ready:**
```python
# Remove these lines:
"local_delivery_plan_id": route_group_id,   # DEPRECATED legacy key
"delivery_plan_id": route_plan_id,          # DEPRECATED legacy key
```

---

### D.3 — Retire legacy notification target params

**File:** `Delivery_app_BK/sockets/notifications.py`

Two locations pass `"localDeliveryPlanId"` to notification targets (lines 744 and 761). Remove these once the frontend navigation targets no longer read that key:

```python
# BEFORE
params["routeGroupId"] = route_group_id
params["localDeliveryPlanId"] = route_group_id  # DEPRECATED
```
```python
# AFTER
params["routeGroupId"] = route_group_id
```

Also retire `LEGACY_ROUTE_PLAN_ID_KEY`, `LEGACY_ROUTE_GROUP_ID_KEY`, and the related constants at the top of that file, and remove the fallback reads that use them.

---

### D.4 — Retire order request and serializer compatibility aliases

**Files:**
- `Delivery_app_BK/services/requests/order/create_order.py` — remove `delivery_plan_id` input alias, keep only `route_plan_id`
- `Delivery_app_BK/services/commands/order/create_order_import.py` — remove `delivery_plan_id` CSV column mapping
- `Delivery_app_BK/services/queries/order/serialize_order.py` — remove `delivery_plan_id` from output payload
- `Delivery_app_BK/services/requests/order/update_orders_delivery_plan_batch.py` — remove `delivery_plan_id` from allowed snapshot filters

Before retiring each alias, grep for the key in the frontend codebase:
```bash
grep -r "delivery_plan_id" ../Front_end/admin-app/src/
```
Only proceed when the count is zero.

---

### D.5 — Retire delivery_plan query/command wrappers

**Files to retire** (thin wrappers that delegate to canonical implementations):
- `Delivery_app_BK/services/queries/route_plan/list_route_plans.py` — currently wraps `list_delivery_plans`. Inline the canonical implementation directly or redirect callers.
- `Delivery_app_BK/services/queries/route_plan/get_route_plan.py` — wraps `get_plan`. Same.
- `Delivery_app_BK/services/queries/route_plan/plan_states/list_route_plan_states.py` — wraps legacy.
- `Delivery_app_BK/services/queries/route_plan/plan_types/get_route_group_plan_type.py` — wraps `get_local_delivery_plan`.

**Retirement order:** For each wrapper:
1. Grep for the wrapper's import path across the whole codebase.
2. Replace each callsite with the canonical direct import.
3. Delete the wrapper file.
4. Run the full test suite.

---

### D.6 — Retire `emit_local_delivery_plan_updated()` alias

**File:** `Delivery_app_BK/sockets/emitters/local_delivery_plan_events.py`

```python
# Remove this function entirely:
def emit_local_delivery_plan_updated(local_delivery_plan, *, payload=None):
    emit_route_group_updated(local_delivery_plan, payload=payload)
```

Grep for `emit_local_delivery_plan_updated` callsites and replace with `emit_route_group_updated`.

---

### D.7 — Retire `emit_route_solution_deleted()` legacy wrapper

**File:** `Delivery_app_BK/sockets/emitters/route_solution_events.py`

```python
# Remove this function entirely:
def emit_route_solution_deleted(team_id, local_delivery_plan_id, route_solution_id, *, payload=None):
    emit_route_solution_deleted_for_route_group(...)
```

Grep for `emit_route_solution_deleted` callsites and replace with `emit_route_solution_deleted_for_route_group`.

---

### D.8 — Update migration report

After all retirements:
```bash
python scripts/report_route_naming_legacy_refs.py
```

The output should show zero legacy references remaining. If any remain, investigate before closing the migration.

---

## Checklist summary

### Step C (do now)
- [ ] C.1 Fix broken import in `plan_tools.py` / `tool_registry.py`
- [ ] C.2 Rename `local_delivery_plan_id` → `route_plan_id` in `optimize_plan_tool()`
- [ ] C.3 Fix column filter `local_delivery_plan_id` → `route_group_id` in `list_routes_tool()`
- [ ] C.4 Fix `local_delivery_handler.py` relationship and column references
- [ ] C.5 Update `system_prompt.py` `optimize_plan` parameter doc
- [ ] C.6 Update `logistics_execute_prompt.py` parameter docs
- [ ] C.7 Add `route_plan_id` lookups in `response_formatter.py`
- [ ] C.8 Add `route_plan_id` field in `collection_presentation.py`
- [ ] C.9 Update `AI_OPERATOR.md`
- [ ] Run `pytest tests/unit/ai/ -v` and fix all failures

### Step D (after frontend migration is confirmed complete)
- [ ] D.1 Detach `BUSINESS_EVENT_ROUTE_GROUP_UPDATED` from legacy string
- [ ] D.2 Remove legacy payload keys from socket emitters
- [ ] D.3 Remove `localDeliveryPlanId` from notification targets
- [ ] D.4 Retire order request/serializer compat aliases
- [ ] D.5 Retire thin wrapper query files under `route_plan/`
- [ ] D.6 Delete `emit_local_delivery_plan_updated()` alias
- [ ] D.7 Delete `emit_route_solution_deleted()` legacy wrapper
- [ ] D.8 Run migration report, confirm zero legacy refs

---

## Key files quick-reference

| File | What to change |
|---|---|
| `ai/tools/plan_tools.py` | Fix import, rename param, fix column filter |
| `ai/tools/plan_execution/local_delivery_handler.py` | Fix relationship + column refs |
| `ai/prompts/system_prompt.py` | Update optimize_plan param name |
| `ai/prompts/logistics_execute_prompt.py` | Update optimize_plan and create_order param names |
| `ai/response_formatter.py` | Add route_plan_id to key lookups |
| `ai/collection_presentation.py` | Add route_plan_id alongside delivery_plan_id |
| `ai/AI_OPERATOR.md` | Full pass — update all tool signatures and model refs |
| `sockets/contracts/realtime.py` | Step D — detach ROUTE_GROUP_UPDATED from legacy string |
| `sockets/emitters/local_delivery_plan_events.py` | Step D — remove legacy payload keys |
| `sockets/emitters/route_solution_events.py` | Step D — remove legacy payload keys from helper |
| `sockets/notifications.py` | Step D — remove LEGACY_ constants and their fallback reads |
