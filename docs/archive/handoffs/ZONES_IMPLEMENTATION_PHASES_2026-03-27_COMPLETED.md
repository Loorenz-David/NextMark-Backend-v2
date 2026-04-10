# ZONES — Implementation Phases

> This document is the implementation roadmap for the Zones domain.
> It is written for Copilot (worker) with the planner providing context per phase.
> Read `ZONES_CURRENT_STATE_AND_VISION.md` first — it defines the domain language and explains WHY each phase exists.

---

## GROUND RULES FOR COPILOT

- Read the target file before editing it. Never assume current state.
- Follow the layer order: `routers → services/commands or queries → domain → models`
- One migration per schema change. Never alter tables manually.
- Python type hints required on all public function signatures.
- Pydantic V2 for all new request/response schemas.
- No business logic in routers. No ORM calls in routers.
- When backend and frontend phases overlap, backend API contracts must be agreed first. Frontend consumes the contract, not an assumption.
- Mark each task complete only when: code written, migration generated (if needed), serializer correct, router wired, no orphaned imports.

---

## PHASE 1 — Structural Fixes + Domain Skeleton + API Contracts

> Goal: Fix what is broken today, establish the correct structural foundation, and publish the initial API contracts so backend and frontend can develop in parallel from Phase 2 onward.

### 1.1 Fix BUG-1 — `point_to_zone_resolver.py` runtime crash

**File:** `zones/services/point_to_zone_resolver.py`

The resolver calls `zone.centroid` expecting a dict. The `Zone` model has no `.centroid` property — it stores `centroid_lat` and `centroid_lng` as separate float columns.

Tasks:
- Replace all `zone.centroid` dict access with `zone.centroid_lat` and `zone.centroid_lng`
- Remove any `isinstance(centroid, dict)` guard — it is no longer needed
- Update `haversine_distance` call sites to pass `zone.centroid_lat`, `zone.centroid_lng` directly
- Confirm no other file calls `zone.centroid` (grep before closing)

---

### 1.2 Fix BUG-3 — Remove `unique=True` from `RouteGroup.route_plan_id`

**File:** `models/tables/route_operations/route_plan/route_group.py`

The `unique=True` on `route_plan_id` blocks 1:N plan→group relationships.

Tasks:
- Remove `unique=True` from the `route_plan_id` column definition
- Change `RoutePlan.route_group` relationship from `uselist=False` to `uselist=True` and rename it `route_groups`
- Update any code that accesses `route_plan.route_group` (single) to handle `route_plan.route_groups` (list) — search for all usages before changing
- Generate Alembic migration: drop the unique constraint on `route_group.route_plan_id`
- Add a plain index on `route_plan_id` if not already present (it was implicit from unique constraint)

---

### 1.3 Add zone fields to `RouteGroup`

**File:** `models/tables/route_operations/route_plan/route_group.py`

Add the fields that connect a RouteGroup to its originating zone and snapshot its state at creation time.

Fields to add:
```python
zone_id = Column(Integer, ForeignKey("zone.id", ondelete="SET NULL"), nullable=True, index=True)
name = Column(String(255), nullable=True)
zone_geometry_snapshot = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
template_snapshot = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
```

Relationship to add:
```python
zone = relationship("Zone", lazy="selectin")
```

Tasks:
- Add the four columns and one relationship
- Generate Alembic migration for the new columns
- No backfill needed — existing records will have NULL zone_id (acceptable)

---

### 1.4 Create `zone_template` table

**File to create:** `models/tables/zones/zone_template.py`

This is the missing model for reusable operational defaults per zone.

Schema:
```python
class ZoneTemplate(db.Model):
    __tablename__ = "zone_template"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("zone.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    config_json = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=dict)
    # config_json shape:
    # {
    #   "vehicle_type_id": int | null,
    #   "default_service_time_seconds": int | null,
    #   "depot_id": int | null,
    #   "max_stops": int | null,
    #   "constraints": dict | null
    # }
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

Tasks:
- Create the file
- Register `ZoneTemplate` in `models/__init__.py` alongside the other zone models
- Generate Alembic migration
- Add `templates` relationship to `Zone` model: `relationship("ZoneTemplate", back_populates="zone", cascade="all, delete-orphan")`

---

### 1.5 Publish initial API contracts (Backend → Frontend handoff)

Once 1.1–1.4 are complete, document and implement the stable API surface that frontend will consume. These endpoints are the contract — shapes must not change without coordinating both sides.

**Zone endpoints (already exist, verify shapes are correct):**

```
GET  /api_v2/zones/                             → list zone versions
     Response: [{ id, team_id, city_key, version_number, is_active, created_at }]

PUT  /api_v2/zones/                             → create zone version
     Body: { city_key: string }
     Response: { id, team_id, city_key, version_number, is_active, created_at }

PATCH /api_v2/zones/<version_id>/activate       → activate zone version
     Response: { id, ..., is_active: true }

GET  /api_v2/zones/<version_id>/zones           → list zones in version
     Response: [{ id, name, zone_type, centroid_lat, centroid_lng, geometry, is_active }]

PUT  /api_v2/zones/<version_id>/zones           → create zone in version
     Body: { name, zone_type, geometry, centroid_lat, centroid_lng, min_lat, max_lat, min_lng, max_lng }
     Response: { id, name, zone_type, centroid_lat, centroid_lng, geometry, ... }
```

**Zone template endpoints (new — must be implemented):**

```
GET  /api_v2/zones/<version_id>/zones/<zone_id>/template
     Response: { id, zone_id, name, config_json, version, is_active } | null

PUT  /api_v2/zones/<version_id>/zones/<zone_id>/template
     Body: { name, config_json: { vehicle_type_id?, default_service_time_seconds?, depot_id?, max_stops?, constraints? } }
     Response: { id, zone_id, name, config_json, version, is_active }
```

**Route Group endpoints (new — must be implemented):**

```
GET  /api_v2/route-plans/<plan_id>/route-groups
     Response: [{ id, name, zone_id, zone_geometry_snapshot, template_snapshot, driver_id, state, total_orders }]

POST /api_v2/route-plans/<plan_id>/route-groups/materialize
     Body: { zone_ids: int[] }
     Response: [{ id, name, zone_id, ... }]   ← one entry per zone materialized
```

Tasks:
- Implement `services/commands/zones/create_zone_template.py`
- Implement `services/queries/zones/get_zone_template.py`
- Add template routes to `routers/api_v2/zones.py`
- Implement `services/commands/route_plan/materialize_route_groups.py` (see Phase 3)
- Implement `services/queries/route_plan/list_route_groups.py`
- Add route group routes to `routers/api_v2/delivery_plan/` or a new `route_groups.py` router

---

## PHASE 2 — Backend & Frontend Parallel Development

> Prerequisite: Phase 1 complete. API contracts from 1.5 are stable and documented.
> Backend and frontend develop independently against the agreed contracts.

---

### 2-BE — Backend: Zone CRUD + Template Service

**Goal:** Full zone management lifecycle from API to DB.

Tasks:

**2-BE-1: `create_zone_template.py` command**
- File: `services/commands/zones/create_zone_template.py`
- Accepts: `zone_id`, `name`, `config_json`
- Validates zone belongs to team
- Deactivates existing active template for that zone before creating new one
- Returns serialized template

**2-BE-2: `get_zone_template.py` query**
- File: `services/queries/zones/get_zone_template.py`
- Fetches active template for a zone_id + team_id
- Returns None (not 404) if no template exists — callers decide how to handle absence

**2-BE-3: Update zone serializer**
- When serializing a Zone for API responses, include the active template inline if present:
  ```json
  { "id": 1, "name": "Stockholm North", ..., "template": { ... } | null }
  ```

**2-BE-4: Wire template endpoints to router**
- Add to `routers/api_v2/zones.py`:
  - `GET /<version_id>/zones/<zone_id>/template`
  - `PUT /<version_id>/zones/<zone_id>/template`

---

### 2-FE — Frontend: Zone Management Feature Module

> Location: `Front_end/admin-app/src/features/zone/`
> Follow the feature folder contract from `AGENTS.md`: `domain/ api/ actions/ flows/ controllers/ stores/ pages/ components/`

**Goal:** Users can view, create, edit, and activate zone versions with polygon drawing on a map. This is standalone — no dependency on Route Plan integration yet.

Tasks:

**2-FE-1: API layer**
- File: `features/zone/api/zone.api.ts`
- Functions: `fetchZoneVersions`, `createZoneVersion`, `activateZoneVersion`, `fetchZonesForVersion`, `createZone`, `fetchZoneTemplate`, `upsertZoneTemplate`
- All functions call the contracts defined in Phase 1.5
- Response types defined in `features/zone/types/zone.ts`

**2-FE-2: Types**
- File: `features/zone/types/zone.ts`
- Types: `ZoneVersion`, `ZoneDefinition`, `ZoneTemplate`, `ZoneGeometry` (GeoJSON polygon shape)
- No raw backend DTOs exposed beyond the `api/` folder

**2-FE-3: Store**
- File: `features/zone/store/zone.store.ts`
- State: active version, list of zones for active version, selected zone id
- Actions: setActiveVersion, setZones, setSelectedZone

**2-FE-4: Zone map component**
- File: `features/zone/components/ZoneMapLayer.tsx`
- Renders zone polygons from GeoJSON geometry onto the map
- Supports: display only mode, editable mode (draw/edit polygon)
- Does not own any state — receives zones as props, emits geometry changes up

**2-FE-5: Zone version management page**
- File: `features/zone/pages/ZoneManagement.page.tsx`
- Lists versions with active indicator
- Create version flow
- View/edit zones within a version
- Activate version button with confirmation

**2-FE-6: Zone template form**
- File: `features/zone/components/ZoneTemplateForm.tsx`
- Fields: name, vehicle type (select), service time (seconds), depot (optional), max stops (optional)
- Submits via `upsertZoneTemplate` API call

---

## PHASE 3 — Order Assignment Correctness

> Prerequisite: Phase 1 complete. Zone templates and geometry are in place.
> Fix the core spatial logic so order assignment is accurate.

### 3.1 Implement point-in-polygon resolution

**File:** `zones/services/point_to_zone_resolver.py`

Replace the centroid-distance-only resolver with a two-stage strategy:

**Stage 1 — Point-in-polygon (primary)**
- For each zone with a `geometry` GeoJSON polygon, test whether the order's coordinates fall inside the polygon
- Use the `shapely` library: `shapely.geometry.shape(zone.geometry).contains(Point(lng, lat))`
  - Note: GeoJSON coordinates are `[longitude, latitude]` — Shapely Point is `Point(lng, lat)`
- If exactly one zone contains the point → use it, method = `polygon_direct`
- If multiple zones contain the point (overlapping) → use the one with highest zone_type priority (user > system > bootstrap)
- If zero zones contain the point → fall through to Stage 2

**Stage 2 — Centroid nearest-neighbor (fallback)**
- Use existing haversine distance logic (after BUG-1 fix from Phase 1.1)
- Set method = `centroid_fallback`
- Only reached when polygon test finds no match

Tasks:
- Add `shapely` to `requirements.txt`
- Rewrite `resolve_point_to_zone` with the two-stage strategy above
- Return a named tuple or dataclass: `ZoneResolution(zone, method)` so callers know which method was used
- Update `order_assignment_service.py` to use the returned method to set `assignment_method` correctly (fixes BUG-2)

---

### 3.2 Update `order_assignment_service.py` to use resolution method

**File:** `zones/services/order_assignment_service.py`

After calling `resolve_point_to_zone`, use the returned `method` field to set `assignment_method` on the `OrderZoneAssignment` record. Do not hard-code `centroid_fallback` for all coordinate-based resolutions.

---

### 3.3 Add `polygon_miss` unassigned reason

Currently the `unassigned_reason` enum has `polygon_miss` defined but it is never set. After implementing point-in-polygon:
- If coordinates are valid but the point falls outside all polygons AND centroid fallback also fails → set `unassigned_reason = "polygon_miss"`

---

## PHASE 4 — Zone-to-RouteGroup Materialization

> Prerequisite: Phases 1, 2, and 3 complete.
> This is where zones become operational — they are instantiated into Route Groups.

### 4.1 Backend: Materialization command

**File to create:** `services/commands/route_plan/materialize_route_groups.py`

This command is the bridge between the zone system and the route planning system.

Logic:
```
Input:
  - route_plan_id: int
  - zone_ids: list[int]
  - ctx: ServiceContext (team_id, user)

For each zone_id:
  1. Load Zone from DB — verify team_id matches
  2. Load active ZoneTemplate for that zone (if exists)
  3. Create RouteGroup:
       route_plan_id = route_plan_id
       zone_id = zone.id
       name = f"{zone.name}"  (human label)
       zone_geometry_snapshot = zone.geometry  (copy at this moment)
       template_snapshot = template.config_json if template else {}
  4. Apply template defaults to RouteGroup where applicable
     (e.g. if template has default_service_time_seconds, store it)

Output:
  - List of created RouteGroup serialized dicts
```

Constraints:
- If any zone_id is invalid or belongs to another team → raise ValidationFailed, rollback entire transaction
- If a RouteGroup for this plan+zone already exists → skip (idempotent), do not duplicate
- All groups created in one transaction

---

### 4.2 Backend: Route Group queries

**File to create:** `services/queries/route_plan/list_route_groups.py`

Returns all route groups for a plan with:
- zone info (name, city_key, geometry)
- template_snapshot
- driver (if assigned)
- state
- order count
- active route solution summary (if selected)

---

### 4.3 Backend: Connect order assignment to Route Groups

**File:** `services/commands/route_plan/materialize_route_groups.py` (same as 4.1)

After Route Groups are materialized, query all orders currently assigned to each zone and link them to the corresponding Route Group. Orders assigned to a zone that is part of this plan should be queryable by route group.

This does NOT move orders between plans — it populates the grouping view within the plan.

---

### 4.4 Frontend: Route Plan creation with zone selection

> Location: `features/plan/` (extend existing plan feature)

**Goal:** When a user creates or edits a Route Plan, they can select which zones to include. The system materializes Route Groups from those zones.

Tasks:

**4-FE-1: Zone selection step in Plan form**
- Extend `features/plan/forms/planForm/` with a zone selection step
- Display available zones on a map (reuse `ZoneMapLayer` from Phase 2-FE-4)
- User checks/unchecks zones to include in the plan
- Selected zone ids are submitted with the plan creation/update

**4-FE-2: Materialization trigger**
- After plan is created, call `POST /api_v2/route-plans/<plan_id>/route-groups/materialize`
- Pass selected zone_ids
- On success: navigate to plan detail showing route groups

**4-FE-3: Route Group list view**
- File: `features/plan/routeGroup/components/RouteGroupList.tsx`
- Displays each Route Group as a card: zone name, stop count, driver assignment, state, active solution summary
- Each card links to the Route Group detail (solution management)

**4-FE-4: API layer additions**
- File: `features/plan/api/plan.api.ts` (extend) or `features/plan/routeGroup/api/routeGroup.api.ts` (new)
- Functions: `fetchRouteGroups(planId)`, `materializeRouteGroups(planId, zoneIds)`

---

## PARALLEL DEVELOPMENT CONTRACT

The following table defines the exact handoff between backend and frontend at each phase boundary. Frontend must not begin a phase until the backend contract for that phase is stable.

| Phase | Backend delivers | Frontend can start |
|---|---|---|
| Phase 1 complete | Zone CRUD API (verified), RouteGroup model with zone fields, API contract doc | Zone feature module scaffolding, type definitions |
| Phase 1.5 API contracts published | All endpoints with request/response shapes | API layer implementation, store, components |
| Phase 2-BE complete | Zone template endpoints working | Zone template form, full zone management page |
| Phase 3 complete | Assignment method field reliable, polygon resolution live | No FE dependency on this phase |
| Phase 4.1 + 4.2 complete | Materialization endpoint + route group list endpoint | Plan form zone selection, route group list view |

---

## WHAT IS EXPLICITLY OUT OF SCOPE FOR THESE PHASES

- AI Operator zone tools — deferred until the manual workflow is stable end-to-end
- Auto-zone generation (clustering from order density) — V2 feature
- Zone versioning history UI — V2 feature
- Multi-depot zone overlays — V2 feature
- Time-based (dynamic) zones — V2 feature
- Zone performance analytics dashboard — V2 feature

These are tracked in `ZONES_CURRENT_STATE_AND_VISION.md` section 10 (Extensions Planned).

---

## Addendum — Corrections Completion (2026-03-27)

Status: Completed
Completed at: 2026-03-27 13:00:13 CET

This archived phase plan was later supplemented by a corrections wave documented in:
- `docs/implemented/ZONES_CORRECTIONS_PLAN_2026-03-26.md`

All corrections listed in that plan were implemented in backend code, including:
- Route-plan route-group URL casing alignment to kebab-case (`route-groups`).
- Zone update operation (`PATCH /api_v2/zones/<version_id>/zones/<zone_id>`).
- Zone delete operation (`DELETE /api_v2/zones/<version_id>/zones/<zone_id>`).
- Route-group delete operation (`DELETE /api_v2/route_plans/<route_plan_id>/route-groups/<route_group_id>`).
- Create-zone response shape consistency (`template: null` field).

Validation evidence:
- Focused correction/polish tests passed.
- Non-AI backend unit suite passed:
     - `pytest tests/unit --ignore=tests/unit/ai`
     - Result at completion: 247 passed, 1 warning.

This file remains archived for historical traceability only.
