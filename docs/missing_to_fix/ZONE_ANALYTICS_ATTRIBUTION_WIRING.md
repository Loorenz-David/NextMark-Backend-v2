# Zone Analytics Attribution — Wiring Gap

Date: 2026-03-27
Status: Deferred — implement after manual zone workflow is fully stable and tested
Priority: LOW

---

## What Exists

`Delivery_app_BK/analytics/zone_attribution.py` contains `derive_route_zone(route_solution)`.

### What it does
Implements a majority-stop strategy to determine which zone a RouteSolution "belongs to":
1. Collects all `OrderZoneAssignment` records for every stop in the solution
2. Counts zone frequency across stops
3. If a single zone covers >= 60% of stops → returns `(zone_id, zone_version_id)`
4. Otherwise returns `(None, None)`

The function is correct and standalone. It has no side effects. It does not write to the database.

---

## What Is Missing

`derive_route_zone` is **never called anywhere in the codebase**.

There are no callers. The function produces no data. Zone-based analytics segmentation produces nothing until this is wired in.

---

## Where It Should Be Called

The attribution should be computed and persisted when a RouteSolution is selected as the active solution for a RouteGroup. This is the moment the route's zone identity becomes meaningful for analytics purposes.

### Target call site
`Delivery_app_BK/services/commands/route_plan/local_delivery/route_solution/select_route_solution.py`
(or equivalent command that marks `is_selected = True` on a RouteSolution)

At the point of selection:
1. Call `derive_route_zone(route_solution)` → `(zone_id, zone_version_id)`
2. If result is non-null, persist it — either on the RouteSolution directly (if columns exist) or via a separate analytics record

### What persistence looks like
Two options depending on schema decisions:

**Option A — Add columns to `route_solution`:**
- `attributed_zone_id` (FK → zone.id, SET NULL, nullable)
- `attributed_zone_version_id` (FK → zone_version.id, SET NULL, nullable)
- `zone_attribution_method` (String: `majority_stop | snapshot | unresolved`)

**Option B — Separate analytics table:**
- `route_solution_zone_attribution` table with `route_solution_id`, `zone_id`, `zone_version_id`, `method`, `computed_at`
- Cleaner separation but another join in analytics queries

Option A is simpler and sufficient for the current scope.

---

## Why It Is Deferred

The vision document explicitly states:
> "Do not build AI zone tools until the human-driven zone workflow is complete and tested."

Zone analytics attribution is the bridge between manual execution and future AI reasoning about zone quality. It must not be implemented before:
- Plan creation with zone_ids flow is stable
- Materialization + route group lifecycle is stable
- Route solution selection is tested end-to-end

Once those are stable, implement this as a focused one-sprint addition:
1. Add migration for `attributed_zone_id` / `attributed_zone_version_id` on `route_solution`
2. Wire `derive_route_zone` into the select-solution command
3. Add `attributed_zone_id` to the route solution serializer

---

## Verification Once Implemented

- Selecting a route solution with >60% stops in one zone sets `attributed_zone_id` correctly
- Selecting a mixed-zone solution sets `attributed_zone_id = NULL`
- `zone_attribution.py` has no remaining uncalled-function warnings
- Analytics queries grouping by zone return data after a completed plan cycle
