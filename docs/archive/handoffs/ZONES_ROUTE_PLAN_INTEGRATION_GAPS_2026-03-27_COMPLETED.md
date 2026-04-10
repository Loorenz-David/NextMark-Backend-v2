# Zones — Route Plan Integration Gaps

Created: 2026-03-27
Status: Ready for implementation
Scope: Backend only — 3 gaps in the plan creation flow, plan serialization, and route group total consistency

Read before starting:
- `Back_end/docs/under_development/ZONES_CURRENT_STATE_AND_VISION.md` — domain reference
- `Back_end/Delivery_app_BK/services/commands/route_plan/create_plan.py` — plan creation command
- `Back_end/Delivery_app_BK/services/commands/route_plan/materialize_route_groups.py` — materialization reference
- `Back_end/Delivery_app_BK/services/queries/route_plan/serialize_plan.py` — plan serializer
- `Back_end/Delivery_app_BK/services/domain/route_operations/plan/recompute_plan_totals.py` — existing totals logic

---

## GAP 1 — `create_plan` unconditionally creates a zone-less RouteGroup

**Priority: HIGH — every plan created today gets a ghost route group with no zone, no name, no snapshot.**

### Problem

`create_plan.py` calls `_build_route_group_instances` for every plan, which creates a `RouteGroup`
with `zone_id = None`, `name = None`, `zone_geometry_snapshot = None`, `template_snapshot = None`,
plus a `RouteSolution` with default settings.

In the zones model, route groups must come exclusively from materialization — either:
- Passed as `zone_ids` in the create_plan payload (express path: creates plan + route groups + route solutions in one call)
- Called separately via `POST /route-plans/<id>/route-groups/materialize` after plan creation

The auto-creation of a zone-less group was correct before zones existed. It is now incorrect.

### Intended behavior

**Case A — `zone_ids` provided at plan creation:**
```json
{
  "label": "Deliveries 2026-04-01",
  "start_date": "2026-04-01",
  "zone_ids": [3, 7, 12],
  "route_solution_defaults": { ... }
}
```
1. Create the `RoutePlan`
2. For each zone_id in `zone_ids`:
   - Load the zone (must belong to team, must be active)
   - Load the zone's active template (if any)
   - Create `RouteGroup` with zone snapshot fields populated
   - Create `RouteSolution` pre-filled from zone template defaults (same logic as `_build_route_group_instances` but zone-aware)
3. Return plan + route_groups bundle

**Case B — no `zone_ids` provided:**
1. Create the `RoutePlan` only — no route groups, no route solutions
2. Return plan only
3. Route groups are added later via the materialize endpoint

### What to change

**File: `Delivery_app_BK/services/commands/route_plan/create_plan.py`**

- Remove the unconditional call to `_build_route_group_instances` from the `_apply` loop
- Replace it with a conditional branch:
  - If `item.zone_ids` is a non-empty list → call a new `_build_zone_route_groups(ctx, route_plan, item.zone_ids, item.route_solution_defaults)` that mirrors the materialization logic but inline
  - If `item.zone_ids` is empty or absent → skip route group creation entirely

**File: `Delivery_app_BK/services/requests/route_plan/plan/create_plan.py`**

Add `zone_ids: list[int] = []` to the request schema so it is parsed and validated before reaching the command.

**Zone loading logic in `create_plan`:**

The zone loading in the inline path should use the same guard as `materialize_route_groups.py`:
- Load zones via `Zone.query.filter(Zone.id.in_(zone_ids), Zone.team_id == ctx.team_id, Zone.is_active.is_(True))`
- If any `zone_id` in the list resolves to nothing → raise `ValidationFailed` with the missing IDs listed
- Load the active template per zone via `ZoneTemplate.query.filter_by(team_id, zone_id, is_active=True).first()`
- Build `RouteGroup` with `name=zone.name`, `zone_id=zone.id`, `zone_geometry_snapshot=zone.geometry`, `template_snapshot=template.config_json if template else {}`
- Build `RouteSolution` pre-filled from `template.config_json` fields (vehicle_type_id, default_service_time_seconds, etc.) with the same normalization as the existing `_build_route_group_instances`

**Idempotency:**

Unlike the separate materialize endpoint, the inline path does not need to be idempotent — plan creation is a single atomic operation. Use a regular `db.session.add` without `begin_nested`.

### Serialization impact

When `zone_ids` are provided, the response `created_bundles` must return a list of route groups, not a single `route_group`. Change the bundle structure:
```python
bundle = {
    "delivery_plan": serialize_created_route_plan(route_plan_instance),
    "route_groups": [serialize_created_route_group(rg) for rg in route_group_instances],
}
```
The frontend must handle both shapes: `route_group` (old, zero zones) and `route_groups` (list, zone-aware).

### Verification
- Plan created without `zone_ids` has no route groups in the DB
- Plan created with `zone_ids` has one route group per zone, each with `zone_id`, `name`, `zone_geometry_snapshot`, `template_snapshot` set
- Plan created with an invalid zone_id returns 400
- Existing plan creation tests for the no-zones case still pass

---

## GAP 2 — `get_plan` and `list_route_plans` do not expose route group information

**Priority: HIGH — frontend plan list and detail views cannot show zone state without this.**

### Problem

`serialize_plans` in `serialize_plan.py` does not include any route group information. After materialization,
`GET /route-plans/<id>` returns the plan with no indication of how many route groups exist or what zones
are covered. The frontend must make a second request to `GET /route-plans/<id>/route-groups/` to know this.

For the plan list view this is untenable — loading route group counts for 20 plans would require 20 extra requests.

### What to change

**File: `Delivery_app_BK/services/queries/route_plan/serialize_plan.py`**

Add `route_groups_count` to the serialized output:

```python
"route_groups_count": len(instance.route_groups) if instance.route_groups is not None else 0,
```

This requires `route_groups` to be eager-loaded. Check that `RoutePlan.route_groups` is loaded by the queries
that back `list_route_plans` and `get_plan`. If using lazy loading, add `selectinload(RoutePlan.route_groups)`
to the base query in `list_route_plans.py` and `get_plan.py`.

**For the single-plan `get_plan` response only**, also add an inline `route_groups` summary:

```python
"route_groups": [
    {
        "id": rg.id,
        "name": rg.name,
        "zone_id": rg.zone_id,
        "total_orders": rg.total_orders,
        "state": {"id": rg.state.id, "name": rg.state.name} if rg.state else None,
    }
    for rg in (instance.route_groups or [])
]
```

Keep this summary lean — not the full route group shape. The full shape comes from the separate list endpoint.

**Do not add the full route_groups list to `list_route_plans`** — that would be too expensive for paginated results. `route_groups_count` is sufficient for the list view.

### Verification
- `GET /route-plans/` response includes `route_groups_count` per plan
- `GET /route-plans/<id>` response includes `route_groups_count` and `route_groups` summary list
- Plans with no route groups return `route_groups_count: 0` and `route_groups: []`
- No N+1 query introduced (verify via query logging for list endpoint)

---

## GAP 4 — `total_orders` on RouteGroup goes stale after initial materialization

**Priority: MEDIUM — route group order counts will drift as orders are added, removed, or reassigned.**

### Problem

`RouteGroup.total_orders` is computed once during materialization via a per-zone `COUNT` query on
`OrderZoneAssignment`. After that point, it is never updated. The following events make it stale:

1. An order is added to the plan after materialization
2. An order is removed from the plan
3. An order's zone assignment changes (due to zone version activation triggering reassignment)

The existing `recompute_plan_totals` function (in `services/domain/route_operations/plan/recompute_plan_totals.py`)
recomputes totals on the `RoutePlan` but does not touch individual `RouteGroup.total_orders` counters.

### What to create

**New file: `Delivery_app_BK/services/domain/route_operations/plan/recompute_route_group_totals.py`**

```python
"""Recompute total_orders for all route groups belonging to a route plan."""
```

Logic:
1. Accept a `RoutePlan` instance (already loaded)
2. Load all route groups for the plan that have `zone_id IS NOT NULL`
3. Run a single grouped query:
   ```
   SELECT OrderZoneAssignment.zone_id, COUNT(OrderZoneAssignment.id)
   FROM order_zone_assignment
   JOIN order ON order.id = order_zone_assignment.order_id
   WHERE order.route_plan_id = plan.id
     AND order.team_id = plan.team_id
     AND order_zone_assignment.is_unassigned IS FALSE
     AND order_zone_assignment.zone_id IN [zone_ids from route groups]
   GROUP BY order_zone_assignment.zone_id
   ```
4. Update each `route_group.total_orders` from the result dict (default 0 for zones with no matches)
5. Do NOT commit — caller is responsible for the transaction

This is the same query that already exists in `materialize_route_groups.py` (lines 104–119). Extract it
into this domain function so both paths use the same logic.

### Where to call it

Wire `recompute_route_group_totals(route_plan)` in every command that changes order-plan membership:

| File | Trigger | Add call after |
|---|---|---|
| `services/commands/order/create_order.py` | Order assigned to plan at creation | After plan linkage is applied |
| `services/commands/order/update_order.py` | Order's `route_plan_id` changes | After plan change is applied |
| `services/commands/order/plan_changes/orchestrator.py` | Batch plan changes | After `apply_orders_route_plan_change` |

Also wire it in the zone version activation background job:

| File | Trigger | Add call after |
|---|---|---|
| `services/infra/jobs/tasks/zones.py` | `reassign_orders_for_new_version_job` | After all zone reassignments are committed, for each affected plan |

### What NOT to do

- Do not recompute inside `recompute_plan_totals` — keep the two functions separate. One owns plan-level totals, the other owns route-group-level totals.
- Do not add a DB trigger — this must remain in the Python service layer for traceability.
- Skip recompute for route groups with `zone_id IS NULL` (legacy zone-less groups) — there is no zone assignment to count against.

### Verification
- After adding an order to a plan, the correct route group's `total_orders` increments
- After removing an order from a plan, the correct route group's `total_orders` decrements
- After activating a new zone version (which reassigns orders), all route group totals on active plans reflect the new assignments
- Recompute is idempotent — calling it twice produces the same result

---

## Implementation Order

1. **GAP 2** — serializer change is safe, non-breaking, unblocks frontend immediately
2. **GAP 1** — plan creation flow change; coordinate with frontend on payload and response shape before shipping
3. **GAP 4** — domain function extraction + wiring; do after GAP 1 to avoid double-wiring if create_plan is also a call site

---

## Testing Requirements

| Gap | Test file | What to test |
|---|---|---|
| 1 | `tests/unit/services/commands/plan/test_create_plan_zones.py` | No-zones creates empty plan; with zone_ids creates groups+solutions; invalid zone_id returns 400 |
| 2 | Existing plan serializer tests | `route_groups_count` present; `route_groups` summary on detail endpoint; zero when no groups |
| 4 | `tests/unit/services/domain/plan/test_recompute_route_group_totals.py` | Correct counts after add/remove order; zero for zone_id=NULL groups; idempotent |
