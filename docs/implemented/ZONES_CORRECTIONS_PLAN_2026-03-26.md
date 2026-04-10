# Zones — Corrections & Missing Operations Plan

Created: 2026-03-26
Status: Ready for implementation
Scope: Backend only — 5 gaps identified by planner review against ZONES_CURRENT_STATE_AND_VISION.md

---

## Context

A post-implementation review of the completed zones wave (see ZONES_PLAN_COMPLETION_2026-03-27_12-32-24.md)
identified 5 gaps. All are missing CRUD operations or contract inconsistencies. None require schema changes —
all are service + router additions against the existing models.

Read before starting:
- `Back_end/docs/under_development/ZONES_CURRENT_STATE_AND_VISION.md` — domain rules
- `Back_end/Delivery_app_BK/routers/api_v2/zones.py` — current zone endpoints
- `Back_end/Delivery_app_BK/routers/api_v2/route_plan/plan.py` — current plan endpoints
- `Back_end/Delivery_app_BK/models/tables/zones/zone.py` — Zone model
- `Back_end/Delivery_app_BK/models/tables/route_operations/route_plan/route_group.py` — RouteGroup model

---

## CORRECTION 1 — URL casing: `route_groups` → `route-groups`

**Priority: HIGH — fix before any other correction. The frontend API layer is built against this contract.**

### Problem
The plan router uses underscore paths (`/route_groups/`, `/route_groups/materialize`) but the agreed
API contract in `ZONES_FRONTEND_CONTEXT_AND_PLAN.md` specifies kebab-case (`/route-groups`,
`/route-groups/materialize`). Every other operation path in this router uses kebab-case.

### What to change
File: `Delivery_app_BK/routers/api_v2/route_plan/plan.py`

Change:
```python
@route_plans_bp.route("/<int:route_plan_id>/route_groups/", methods=["GET"])
```
to:
```python
@route_plans_bp.route("/<int:route_plan_id>/route-groups/", methods=["GET"])
```

Change:
```python
@route_plans_bp.route("/<int:route_plan_id>/route_groups/materialize", methods=["POST"])
```
to:
```python
@route_plans_bp.route("/<int:route_plan_id>/route-groups/materialize", methods=["POST"])
```

No logic changes — route decorator strings only.

### Verification
- Both endpoints still respond correctly after rename
- No other file references these URL strings directly (grep for `route_groups/` in routers to confirm)

---

## CORRECTION 2 — Add `update_zone` command and endpoint

**Priority: HIGH — frontend zone management page cannot function without it.**

### Problem
Once a zone is created inside a version, there is no way to edit its name or redraw its polygon.
The only path today is creating an entirely new version. This blocks the zone management UI where
users need to adjust polygons after drawing them.

### Constraints
- A zone can only be updated if its version is **inactive** (`is_active = False`). Editing zones
  in an active version would silently change the source geometry for future route groups while
  leaving existing snapshots untouched — this is allowed by design, but editing geometry of an
  active zone must be a deliberate user action, so for now restrict to inactive versions.
- Centroid and bounding box must be updated together with geometry if geometry changes.
  The client is responsible for sending updated derived fields (same pattern as create).

### Files to create
`Delivery_app_BK/services/commands/zones/update_zone.py`

```python
"""Update name and/or geometry for a zone in an INACTIVE version."""
```

Logic:
1. Load `Zone` by `zone_id`, verify `zone.team_id == ctx.team_id` — else `NotFound`
2. Load `ZoneVersion` for `zone.zone_version_id`
3. If `version.is_active is True` → raise `ValidationFailed("Cannot edit zones in an active version. Create a new version instead.")`
4. Apply only the fields present in `ctx.incoming_data`:
   - `name` (string, non-empty)
   - `geometry` (dict/GeoJSON)
   - `centroid_lat`, `centroid_lng` (floats)
   - `min_lat`, `max_lat`, `min_lng`, `max_lng` (floats)
5. `db.session.commit()`
6. Return serialized zone (same shape as `create_zone`)

### Files to update
`Delivery_app_BK/routers/api_v2/zones.py`

Add endpoint:
```
PATCH /api_v2/zones/<version_id>/zones/<zone_id>
Roles: ADMIN only
Body: { name?, geometry?, centroid_lat?, centroid_lng?, min_lat?, max_lat?, min_lng?, max_lng? }
Response: { id, name, zone_type, centroid_lat, centroid_lng, geometry, ... }
```

### Verification
- Updating a zone in an inactive version succeeds and persists
- Updating a zone in an active version returns 400 with the correct message
- Partial updates (name only, geometry only) work correctly
- Unrecognized fields in body are ignored

---

## CORRECTION 3 — Add `delete_zone` command and endpoint

**Priority: HIGH — zone management UX requires the ability to remove a wrongly added zone.**

### Problem
A zone added to a draft (inactive) version cannot be removed. There is no delete path.

### Constraints
- A zone can only be deleted if its version is **inactive**.
- An active version's zones must not be individually deleted — the versioning model means
  the active set is treated as immutable once published.
- If the zone has any `OrderZoneAssignment` records pointing to it — those use `SET NULL` on the FK,
  so deletion is safe at the DB level. No manual cleanup needed.
- If the zone is referenced by any `RouteGroup.zone_id` — the FK is also `SET NULL`. However,
  a zone being referenced by a route group means it was used in a plan that was likely active.
  Add a guard: if any RouteGroup has `zone_id = zone.id`, raise `ValidationFailed` with a clear
  message explaining that route groups derived from this zone exist.

### Files to create
`Delivery_app_BK/services/commands/zones/delete_zone.py`

```python
"""Delete a zone from an INACTIVE version."""
```

Logic:
1. Load `Zone` by `zone_id`, verify `zone.team_id == ctx.team_id` — else `NotFound`
2. Load `ZoneVersion` for `zone.zone_version_id`
3. If `version.is_active is True` → raise `ValidationFailed("Cannot delete zones from an active version.")`
4. Check `RouteGroup.query.filter_by(zone_id=zone.id).count()` — if > 0 → raise `ValidationFailed("Route groups derived from this zone exist. Remove them before deleting the zone.")`
5. `db.session.delete(zone)`
6. `db.session.commit()`
7. Return `{"deleted": True, "zone_id": zone_id}`

### Files to update
`Delivery_app_BK/routers/api_v2/zones.py`

Add endpoint:
```
DELETE /api_v2/zones/<version_id>/zones/<zone_id>
Roles: ADMIN only
Response: { deleted: true, zone_id: int }
```

### Verification
- Deleting a zone from an inactive version succeeds
- Deleting a zone from an active version returns 400
- Deleting a zone with derived route groups returns 400 with the correct message
- `OrderZoneAssignment` records for the deleted zone have `zone_id` set to NULL (DB cascade, not code)

---

## CORRECTION 4 — Add `delete_route_group` command and endpoint

**Priority: MEDIUM — needed to allow users to undo zone selection mistakes during plan creation.**

### Problem
Once route groups are materialized for a plan, there is no way to remove a specific one.
If a user materializes the wrong zone, the entire plan must be deleted and recreated.

### Constraints
- Cannot delete a route group that has a selected route solution with `actual_start_time` set —
  this means the route is in progress or completed.
- Deleting a route group cascades to its route solutions and stops (model already has
  `cascade="all, delete-orphan"` on `route_solutions`).
- After deletion, the plan's `total_orders` denormalization may be stale — recompute it.

### Files to create
`Delivery_app_BK/services/commands/route_plan/delete_route_group.py`

```python
"""Remove a route group from a plan, provided it has not been executed."""
```

Logic:
1. Load `RouteGroup` by `route_group_id`, verify `route_group.team_id == ctx.team_id` — else `NotFound`
2. Check if any route solution belonging to this group has `actual_start_time IS NOT NULL AND is_selected IS TRUE`:
   - If yes → raise `ValidationFailed("Cannot remove a route group with an in-progress or completed route solution.")`
3. `db.session.delete(route_group)` (cascades to solutions + stops)
4. `db.session.commit()`
5. Return `{"deleted": True, "route_group_id": route_group_id}`

### Files to update
`Delivery_app_BK/routers/api_v2/route_plan/plan.py`

Add endpoint:
```
DELETE /api_v2/route-plans/<route_plan_id>/route-groups/<route_group_id>
Roles: ADMIN, ASSISTANT
Response: { deleted: true, route_group_id: int }
```

Note: Router must verify `route_group.route_plan_id == route_plan_id` to prevent cross-plan tampering.
Add this check inside the command using `ctx.incoming_data.get("route_plan_id")` as a secondary guard.

### Verification
- Deleting a route group with no executed solutions succeeds
- Deleting a route group with `actual_start_time` set on the selected solution returns 400
- Attempting to delete a route group from a different plan returns 404
- Cascade: the route group's solutions and stops are removed from the DB

---

## CORRECTION 5 — `create_zone` response: add `template: null` field

**Priority: LOW — consistency fix. Does not block any functionality.**

### Problem
`list_zones_for_version` returns each zone with `"template": { ... } | null`.
`create_zone` returns a zone dict without the `template` key at all.
This causes a shape mismatch — frontend code that normalizes zone objects will need to
handle both shapes or will silently miss the field after a create.

### What to change
File: `Delivery_app_BK/services/commands/zones/create_zone.py`

In `_serialize_zone`, add `"template": None` to the returned dict.

```python
def _serialize_zone(z: Zone) -> dict:
    return {
        "id": z.id,
        ...existing fields...,
        "template": None,  # newly created zones never have a template yet
    }
```

No logic change. No DB query. The field is always `None` on a newly created zone by definition.

### Verification
- `PUT /api_v2/zones/<version_id>/zones` response includes `"template": null`
- Shape matches the objects returned by `GET /api_v2/zones/<version_id>/zones`

---

## Implementation Order

Execute in this sequence to minimize conflicts:

1. **CORRECTION 1** (URL casing) — must be first, unblocks frontend
2. **CORRECTION 5** (create_zone response) — trivial, do it alongside #1
3. **CORRECTION 2** (update_zone) — independent, do next
4. **CORRECTION 3** (delete_zone) — depends on understanding update_zone pattern
5. **CORRECTION 4** (delete_route_group) — last, slightly more complex guard logic

---

## Testing Requirements

Each correction requires at minimum:

| Correction | Test file location | What to test |
|---|---|---|
| 1 | Existing integration tests | Update any URL strings from `route_groups` to `route-groups` |
| 2 | `tests/unit/services/commands/zones/test_update_zone.py` | Success, inactive-only guard, partial update |
| 3 | `tests/unit/services/commands/zones/test_delete_zone.py` | Success, active-version guard, route-group guard |
| 4 | `tests/unit/services/commands/route_plan/test_delete_route_group.py` | Success, execution guard, cross-plan guard |
| 5 | No new test needed | Covered by verifying response shape manually |

---

## What This Does NOT Change

- Zone versioning lifecycle (create → populate → activate) — unchanged
- Order assignment logic — unchanged
- Materialization logic — unchanged
- All existing serializers except `_serialize_zone` in `create_zone.py`
- Frontend — only the URL casing change (Correction 1) requires frontend coordination
