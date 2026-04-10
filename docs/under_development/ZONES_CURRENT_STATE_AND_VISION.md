# ZONES — Current State, Known Bugs & System Vision

> This document is the authoritative reference for the Zones domain.
> Copilot reads this before touching any zone-related file.
> It covers: what exists today, what is broken, what the system intends to be, and the end goal.

---

## 1. DOMAIN LANGUAGE

These terms are used precisely throughout this codebase. Do not substitute synonyms.

| Term | Meaning |
|---|---|
| **Zone Definition** | Persistent spatial boundary (polygon) owned by a team. Long-lived. Reusable across plans. |
| **Zone Version** | Immutable container grouping all Zone Definitions for a given `(team_id, city_key)` at a point in time. Only one version is active per team+city. |
| **Zone Template** | Reusable operational config attached to a Zone Definition. Holds vehicle type, service time rules, depot, constraints. NOT execution state. |
| **Route Plan** | Date-scoped execution scope. Owns Route Groups. Example: "Deliveries for 2026-04-01". |
| **Route Group** | Plan-scoped operational partition derived from a Zone Definition. Snapshots geometry and template at creation. Immutable to future zone changes. |
| **Route Solution** | Versioned optimization candidate inside a Route Group. Multiple solutions can exist per group. |
| **Order Zone Assignment** | The persisted record of which zone an order belongs to, how it was determined, and why it may have failed. |

---

## 2. WHAT EXISTS TODAY

### 2.1 Database Tables

#### `zone` (`models/tables/zones/zone.py`)
Stores individual spatial zones within a version.

Fields:
- `id`, `team_id`, `zone_version_id`
- `city_key` — normalized city identifier
- `name`
- `zone_type` — enum: `bootstrap | system | user`
- `centroid_lat`, `centroid_lng` — stored as separate float columns
- `geometry` — GeoJSON polygon stored as JSONB
- `min_lat`, `max_lat`, `min_lng`, `max_lng` — bounding box for pre-filtering
- `is_active`
- `created_at`, `updated_at`

Indexes: team+version+active, team+city+version, team+city+version+bbox.

#### `zone_version` (`models/tables/zones/zone_version.py`)
Groups zones for a `(team_id, city_key)` at a version number. Only one version is active per team+city (enforced by partial unique index).

Fields:
- `id`, `team_id`, `city_key`
- `version_number` — auto-incremented per team+city
- `is_active`
- `created_at`

#### `order_zone_assignment` (`models/tables/zones/order_zone_assignment.py`)
The persisted assignment of an order to a zone. One record per order (unique on `order_id`).

Fields:
- `id`, `team_id`, `order_id`, `zone_id` (nullable), `zone_version_id` (nullable), `city_key`
- `assignment_type` — enum: `auto | manual`
- `assignment_method` — enum: `polygon_direct | centroid_fallback | bootstrap_fallback | manual_override`
- `is_unassigned` — true when no zone could be resolved
- `unassigned_reason` — enum: `no_coordinates | no_candidate_zone | polygon_miss | below_threshold`
- `assigned_at`, `updated_at`

---

### 2.2 Service Layer

#### Commands (`services/commands/zones/`)
- `create_zone_version.py` — creates an inactive version for a (team, city_key), auto-increments version_number
- `create_zone.py` — adds a zone record to an existing version
- `activate_zone_version.py` — activates a version (deactivates the previous one), then enqueues a background job to reassign recent orders

#### Queries (`services/queries/zones/`)
- `list_zone_versions.py` — lists versions for a team, filterable by city_key
- `list_zones_for_version.py` — lists all zones in a specific version

#### Zone Services (`zones/services/`)
- `city_key_normalizer.py` — normalizes city strings to lowercase keys
- `version_resolver.py` — fetches the active zone version for a (team, city_key)
- `order_assignment_service.py` — upserts an order's zone assignment. Priority: manual override → coordinate-based → unassigned
- `point_to_zone_resolver.py` — resolves a lat/lng to a zone within a version using centroid distance

#### Background Jobs (`services/infra/jobs/tasks/zones.py`)
- `reassign_orders_for_new_version_job` — when a new zone version is activated, re-runs zone assignment for all orders created within the last 7 days in that city

#### Analytics (`analytics/zone_attribution.py`)
- `derive_route_zone` — given a RouteSolution, determines which zone the route "belongs to" using a 60% majority-stop threshold

#### API Router (`routers/api_v2/zones.py`)
Endpoints:
- `GET /api_v2/zones/` — list zone versions
- `PUT /api_v2/zones/` — create a new zone version
- `PATCH /api_v2/zones/<version_id>/activate` — activate a version
- `GET /api_v2/zones/<version_id>/zones` — list zones in a version
- `PUT /api_v2/zones/<version_id>/zones` — add a zone to a version

---

### 2.3 Route Operations Tables (zone-adjacent)

#### `route_plan` (`models/tables/route_operations/route_plan/route_plan.py`)
Date-scoped plan. Has label, date_strategy (single/range), start_date, end_date, state. No zone reference.

#### `route_group` (`models/tables/route_operations/route_plan/route_group.py`)
Currently: execution container for a plan. Has driver, vehicle reference via solution, route_solutions relationship.

**Critical structural issue:** `route_plan_id` has `unique=True`, meaning one RoutePlan can only have ONE RouteGroup. The spec requires one RouteGroup per zone. This constraint blocks the multi-zone architecture entirely.

**No zone fields exist on RouteGroup.** There is no `zone_definition_id`, no `zone_geometry_snapshot`, no `template_snapshot`.

#### `route_solution` (`models/tables/route_operations/route_plan/route_solution.py`)
Versioned optimization candidate. Has `version`, `is_selected`, `is_optimized`, `route_group_id`. Well-structured for multi-version iteration.

---

## 3. KNOWN BUGS

### BUG-1 — `point_to_zone_resolver.py` will crash at runtime (AttributeError)
**File:** `zones/services/point_to_zone_resolver.py`, lines 90–97

**Problem:** The resolver accesses `zone.centroid` as a dict property expecting keys `lat` and `lng`. The `Zone` model does **not** have a `.centroid` property. It stores centroid as two separate columns: `centroid_lat` and `centroid_lng`.

**Effect:** Any call to `resolve_point_to_zone` will raise `AttributeError: 'Zone' object has no attribute 'centroid'` the moment a zone with coordinates is evaluated.

**Fix:** Replace `centroid = zone.centroid` with direct column access: use `zone.centroid_lat` and `zone.centroid_lng`.

---

### BUG-2 — `assignment_method` is set to `centroid_fallback` when it should be `polygon_direct`
**File:** `zones/services/order_assignment_service.py`, line 112

**Problem:** The comment on that line even acknowledges this: `# or polygon_direct if implementing point-in-polygon`. The `assignment_method` field is set to `centroid_fallback` for all coordinate-based resolutions, which is technically incorrect since `polygon_direct` is the intended primary method.

**Effect:** Data quality issue — historical assignment records cannot be trusted to distinguish "resolved by polygon" from "resolved by centroid nearest neighbor". This must be fixed once point-in-polygon is implemented.

---

### BUG-3 — 1:1 constraint between RoutePlan and RouteGroup blocks the architecture
**File:** `models/tables/route_operations/route_plan/route_group.py`, line 42

**Problem:** `route_plan_id = Column(..., unique=True, ...)`. This enforces a hard one-to-one relationship between plans and groups.

**Effect:** Multi-zone plans (one plan → many route groups, one per zone) are structurally impossible until this unique constraint is removed via migration.

---

### BUG-4 — RouteGroup has no zone connection
**File:** `models/tables/route_operations/route_plan/route_group.py`

**Problem:** There are no fields linking a RouteGroup to any Zone Definition, nor any snapshot fields. Zone assignments and route groups are two disconnected systems with no structural bridge.

**Effect:** You cannot query "which zone does this route group cover", cannot snapshot zone geometry for historical correctness, and cannot apply zone templates to route configuration.

---

## 4. WHAT THE SYSTEM INTENDS TO BE

### 4.1 Zones as Persistent Infrastructure
Zones are **not** owned by a plan. They are long-lived spatial definitions that persist across many plans. A team builds their zone map once and reuses it every day.

Zone Definitions are the "what" — the named geographic areas the business cares about.
Zone Templates are the "how" — the default operational configuration for operating in that zone.

### 4.2 Route Groups as Zone Snapshots
When a Route Plan is created and zones are selected, the system **materializes** one Route Group per zone. At that moment, the zone's current geometry and template config are snapshotted into the Route Group. From that point forward, the Route Group is independent — changes to the Zone Definition do not retroactively alter the plan.

This is the snapshot immutability principle. It is non-negotiable for historical correctness.

### 4.3 Order Assignment via Point-in-Polygon
Orders are assigned to zones when they are created or when a new zone version is activated. The primary strategy is **point-in-polygon** — an order's delivery coordinates are tested against each zone's GeoJSON geometry. Centroid distance is a fallback when polygon resolution fails. Manual override is always available.

### 4.4 Multi-Version Zone Management
Zone Definitions evolve over time. When a team updates their zone map, they create a new version (inactive), populate it with updated zones, then activate it. Activation triggers background reassignment of recent orders. Old Route Groups retain their snapshots. New plans use the current active version.

### 4.5 Cross-Domain Utility
Zones are not routing-only infrastructure. They are a spatial primitive usable across:
- Route planning (primary use today)
- Pricing regions
- SLA enforcement
- Analytics segmentation
- Warehouse coverage boundaries

---

## 5. DATA MODEL — TARGET STATE

### `zone` (current — mostly correct, needs centroid property fix)
No schema changes required beyond ensuring correct property access in service layer.

### `zone_template` (MISSING — must be created)
```
id                  PK
zone_id             FK → zone.id (CASCADE)
team_id             FK → team.id (CASCADE)
name                String
config_json         JSONB
  vehicle_type_id     optional FK reference (stored as int in json)
  default_service_time_seconds  int
  depot_id            optional
  max_stops           optional int
  constraints         optional dict
version             Integer, default 1
is_active           Boolean, default True
created_at          UTCDateTime
```

### `route_group` (must be updated)
Remove `unique=True` from `route_plan_id`.
Add:
```
zone_id                   FK → zone.id (SET NULL)  -- reference only, not binding
name                      String  -- human label, e.g. "Stockholm North - 2026-04-01"
zone_geometry_snapshot    JSONB   -- geometry at instantiation time
template_snapshot         JSONB   -- zone template config at instantiation time
```

### `route_plan` (no changes needed)
Already has label, date_strategy, start_date, end_date, state. Correct as-is.

### `route_solution` (no changes needed)
Already versioned, selectable, with metrics. Correct as-is.

---

## 6. FULL SYSTEM LIFECYCLE (TARGET)

```
1. Team builds zone map
   → Create ZoneVersion (inactive)
   → Add ZoneDefinitions (with geometry polygons)
   → Attach ZoneTemplates (optional operational defaults)
   → Activate version → triggers background order reassignment

2. Order created
   → Zone assignment triggered automatically
   → Primary: point-in-polygon against active version
   → Fallback: centroid nearest-neighbor
   → Fallback: unassigned (tracked with reason)

3. Route Plan created
   → User selects zones to include
   → System materializes one RouteGroup per zone:
       - snapshots geometry
       - snapshots template config
       - applies template defaults to RouteGroup settings
   → Orders are now grouped by zone assignment

4. Route Optimization
   → Per RouteGroup: send orders to optimizer
   → Optimizer returns RouteSolution (versioned)
   → Multiple solutions can be generated and compared
   → User selects the preferred solution

5. Execution
   → Drivers assigned to selected RouteSolutions
   → Live tracking updates route stop actual times
   → Analytics aggregation uses zone attribution for segmentation
```

---

## 7. END GOAL

The zone system should become the **spatial brain** of the logistics platform.

**Stable system (build first):**
- Zones define the operational geography of the team
- Route Plans consume zones and materialize them into executable Route Groups
- Order assignment is spatially accurate (polygon-based)
- Zone changes never corrupt historical plan data (snapshot immutability)
- Analytics can segment all metrics by zone

**AI layer (build after the manual system is stable — explicitly deferred):**
The AI Operator should not be expanded to consume zones until the zone system works correctly end-to-end without AI involvement. Once stable, the AI operator will reason about:
- Zone quality (too large, density imbalance)
- Operational fit (capacity vs stop count, SLA violations)
- Optimization suggestions (split, merge, shift boundary)
- Auto-zone generation from order clusters (V2)

Do not build AI zone tools until the human-driven zone workflow is complete and tested.

---

## 8. FILE MAP — ZONE DOMAIN

```
Back_end/
  Delivery_app_BK/
    models/tables/zones/
      zone.py                           -- Zone Definition table
      zone_version.py                   -- Zone Version table
      order_zone_assignment.py          -- Order → Zone assignment table
      [zone_template.py]                -- MISSING — must be created

    models/tables/route_operations/route_plan/
      route_group.py                    -- needs zone_id, snapshots, remove unique constraint
      route_plan.py                     -- correct as-is
      route_solution.py                 -- correct as-is

    zones/services/
      city_key_normalizer.py            -- normalize city strings
      version_resolver.py               -- fetch active zone version
      order_assignment_service.py       -- upsert order zone assignment (BUG-2 here)
      point_to_zone_resolver.py         -- centroid resolver (BUG-1 here, polygon TBD)

    services/commands/zones/
      create_zone_version.py
      create_zone.py
      activate_zone_version.py
      [create_zone_template.py]         -- MISSING
      [materialize_route_groups.py]     -- MISSING

    services/queries/zones/
      list_zone_versions.py
      list_zones_for_version.py
      [get_zone_with_template.py]       -- MISSING

    services/infra/jobs/tasks/
      zones.py                          -- background order reassignment

    analytics/
      zone_attribution.py               -- derive zone from route majority-stop

    routers/api_v2/
      zones.py                          -- zone version + zone CRUD endpoints
      [route_groups needs zone endpoints] -- MISSING

Front_end/
  admin-app/src/features/
    [zone/]                             -- MISSING — no zone feature module exists
    plan/                               -- needs zone integration in plan creation flow
```
