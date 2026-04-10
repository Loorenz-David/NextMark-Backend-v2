# AI Operator — Phase 2 Narrative Snapshot Tools: Implementation Summary

**Date:** 2026-04-01
**Plan:** `docs/archive/AI_OPERATOR_PHASE_2_NARRATIVE_SNAPSHOT_TOOLS_2026-04-01.md`
**Status:** ✅ Fully implemented and verified

---

## What Was Implemented

### 1. `ai/tools/geometry_utils.py` — Created (new file)
Pure-Python spatial helpers. No Flask context, no DB, no side effects.
- `haversine_m(lat1, lng1, lat2, lng2)` — great-circle distance in meters
- `centroid(points)` — mean lat/lng of a point list
- `max_radius_m(center, points)` — max distance from center to any point
- `point_within_corridor(candidate, stop_points, buffer_m)` — corridor check
- `cheapest_insertion(stop_points, candidate)` — optimal insertion point + detour cost
- `eta_tolerance_to_buffer_m(eta_tolerance_seconds)` — tolerance → spatial buffer (min 300 m)
- `meters_to_seconds(meters, speed_mps)` — travel time estimate

### 2. `ai/tools/narrative_tools.py` — Fully implemented (was NotImplementedError stubs)
Three snapshot tools, each returning a `blocks` list of NarrativeBlock dicts:

- **`get_plan_snapshot_tool(ctx, plan_id)`**: health view of a plan. Calls `get_plan` + `list_route_groups`, builds KPI/breakdown/insight/warning blocks (total orders, group breakdown, optimization status, unzoned orders).
- **`get_route_group_snapshot_tool(ctx, route_group_id)`**: deep-dive on one route group. Calls `get_route_group`, builds blocks for order state distribution, active route distance/travel time, driver assignment, constraint violations, stale ETAs, out-of-range stops.
- **`get_operations_dashboard_tool(ctx, date)`**: cross-plan view for a date. Calls `find_plans`, builds aggregate KPI/breakdown/insight/warning blocks across all active plans.

Shared private helpers at module level:
- `_ORDER_STATE_ID_TO_NAME` / `_PLAN_STATE_ID_TO_NAME` reverse maps from system_prompt state maps
- `_state_counts_to_named(raw)` — converts `{str(id): count}` JSONB → `{state_name: count}`
- `_plan_state_name(state_id)` — safe integer → name lookup

### 3. `ai/tools/zone_tools.py` — Partially implemented
- **`evaluate_order_route_fit_tool(ctx, route_solution_id, order_id)`** — IMPLEMENTED. Loads `RouteSolution` + its stops, collects stop `client_address.coordinates`, loads candidate `Order.client_address.coordinates`, runs corridor check + cheapest-insertion detour estimate, returns full result dict with blocks.
- `list_zones_tool` / `get_zone_snapshot_tool` — remain Phase 3 NotImplementedError stubs (confirmed correct per plan).

### 4. `ai/tool_registry.py` — 5 tools registered
```python
TOOLS = {
    "get_plan_snapshot":         get_plan_snapshot_tool,
    "get_route_group_snapshot":  get_route_group_snapshot_tool,
    "get_operations_dashboard":  get_operations_dashboard_tool,
    "evaluate_order_route_fit":  evaluate_order_route_fit_tool,
    "geocode_address":           geocode_address_tool,
}
```
`geocode_address_tool` from `tools/geocode_tools.py` registered here (file not modified).

### 5. `ai/response_formatter.py` — Registry entries added
Added 5 summary functions and 5 action functions, replacing the empty commented registries:
- `_SUMMARY_REGISTRY`: 5 entries matching TOOLS keys
- `_ACTION_REGISTRY`: 5 entries matching TOOLS keys
- Navigation actions wired for `get_plan_snapshot` (→ `/plans/<id>`) and `get_route_group_snapshot` (→ `/plans/<id>?group=<id>`) and `get_operations_dashboard` (→ `/plans`)
- `evaluate_order_route_fit` and `geocode_address` return empty action lists (AI decides next step)

### 6. `ai/prompts/system_prompt.py` — AVAILABLE TOOLS section replaced
Replaced the "No tools are currently registered" placeholder with full documentation for all 5 tools: parameter tables, return field lists, usage guidance, and the `PREREQUISITE` note for `evaluate_order_route_fit`.

### 7. `ai/AI_OPERATOR.md` — Updated
- Module Structure: added `tools/geometry_utils.py`
- "Tool Registry Status (Phase 1)" → replaced with "Registered Tools (Phase 2)" table
- "Tool File Status (Phase 1)" → replaced with "Tool File Status (Phase 2)" with implemented/skeleton/stub breakdown
- Prompt Architecture section: updated current policy note
- "Next Phases" section: updated to Phase 3 (Core Query Tools) + Phase 4 (Mutation Tools)

---

## Verification Results

All plan verification checks passed:

```
haversine_m: 1248.2 m (>0 OK)
point_within_corridor: True OK
cheapest_insertion: best_index=1 OK
TOOLS: 5 keys OK
SUMMARY_REGISTRY: 5 OK
ACTION_REGISTRY: 5 OK
system_prompt tool docs OK
list_zones_tool NotImplementedError stub OK
get_zone_snapshot_tool NotImplementedError stub OK

All Phase 2 verification checks passed.
```

---

## Not Implemented (and Why)

Nothing was skipped in this phase. All items from the plan were completed.

The following were intentionally left as stubs per the plan's explicit instructions:
- `list_zones_tool` — deferred to Phase 3 (plan says "DO NOT implement in Phase 2")
- `get_zone_snapshot_tool` — deferred to Phase 3 (same)
- All mutation tools (order/plan/item) — Phase 4

---

## Files Modified

| File | Change |
|---|---|
| `ai/tools/geometry_utils.py` | CREATED |
| `ai/tools/narrative_tools.py` | Implemented (was stubs) |
| `ai/tools/zone_tools.py` | Added `evaluate_order_route_fit_tool` |
| `ai/tool_registry.py` | Registered 5 tools |
| `ai/response_formatter.py` | Added summary + action functions and populated registries |
| `ai/prompts/system_prompt.py` | Replaced AVAILABLE TOOLS placeholder with full docs |
| `ai/AI_OPERATOR.md` | Updated registered tools table, file status, next phases |

## Files NOT Modified (per plan's DO NOT TOUCH list)

`orchestrator.py`, `planner.py`, `thread_store.py`, `errors.py`, `schemas.py`,
`providers/*`, `tools/plan_tools.py`, `tools/order_tools.py`, `tools/item_tools.py`,
`tools/plan_execution/*`, `tools/geocode_tools.py`
