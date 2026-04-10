# Route Group, Route Lanes, and Draft Promotion Plan

Status: Proposed
Date: 2026-03-30
Scope: Back_end route-plan domain

## 1) Intention

The current model has one RouteGroup per (team, plan, zone), and each RouteGroup can hold many RouteSolution records.

Today, RouteSolution is used as a single selected variant in many places. Product intent is evolving toward two distinct concepts:

- Parallel execution lanes inside a zone (multiple vehicles running in the same zone at the same time)
- Safe experimentation on each lane without losing the currently shippable configuration

This plan formalizes:

- RouteGroup = zone container for one plan
- RouteSolution = execution lane (one vehicle/driver/start-end/time set)
- RouteSolutionDraft = editable experiments for one lane

## 2) Goal

Deliver a model that supports all of the following with minimal migration risk:

- Multiple active route lanes for one zone RouteGroup
- Draft experimentation per lane
- Explicit promotion flow from draft to lane
- Deterministic defaults from ZoneTemplate into newly created lanes
- Backward compatibility with current API and existing data

## 3) Current Constraints and Why They Still Work

Current RouteGroup uniqueness is already aligned with the target:

- UniqueConstraint(team_id, route_plan_id, zone_id)
- Interpretation: one zone container per plan

This should remain unchanged.

Current RouteSolution shape is also largely reusable:

- Holds one driver_id, one vehicle_id, one start/end location, one set_start/set_end time
- This maps well to one executable lane

Main change needed is semantic:

- RouteSolution is no longer "single winner variant"
- RouteSolution becomes "lane that can be active alongside other lanes in same RouteGroup"

## 4) Contract: Table-Level Design

### 4.1 Keep RouteGroup as-is

Table: route_group

No schema change required for this proposal.

Reason:
- One group per zone per plan is desirable
- Orders stay grouped by zone container
- Aggregations remain stable

### 4.2 Evolve RouteSolution semantics (minimal additive change)

Table: route_solution

Keep existing columns and add these columns:

- lane_status (String, nullable=False, default="planned", index=True)
  - Allowed: planned, ready, dispatched, closed, canceled
- lane_index (Integer, nullable=True)
  - Optional stable ordering inside the group (1..N)
- is_dispatch_target (Boolean, nullable=False, default=True, index=True)
  - Replaces old meaning of single-winner is_selected

Keep existing is_selected for backward compatibility in phase 1.

Compatibility rule during transition:

- if is_selected is true, treat as is_dispatch_target true
- no uniqueness constraint on is_selected
- no uniqueness constraint on is_dispatch_target

Why additive:
- avoids risky destructive migration
- preserves current reads while new semantics are introduced

### 4.3 Add new RouteSolutionDraft table

Table: route_solution_draft

Columns:

- id (PK)
- team_id (FK team, indexed)
- route_solution_id (FK route_solution ondelete CASCADE, indexed)
- version (Integer, nullable=False)  # monotonically increasing per route_solution
- is_active_draft (Boolean, nullable=False, default=True, index=True)
- source (String, nullable=True)  # user, ai, clone, system_seed
- note (String, nullable=True)

Editable payload fields (copy of lane-config fields only):

- start_location (JSONB)
- end_location (JSONB)
- set_start_time (String)
- set_end_time (String)
- route_end_strategy (Enum/string same domain as route_solution)
- eta_tolerance_seconds (Integer)
- stops_service_time (JSONB)
- start_facility_id (FK facility, nullable)
- end_facility_id (FK facility, nullable)
- driver_id (FK user, nullable)
- vehicle_id (FK vehicle, nullable)

Audit fields:

- created_at (UTCDateTime)
- updated_at (UTCDateTime)
- promoted_at (UTCDateTime, nullable)
- promoted_by_user_id (FK user, nullable)

Constraints:

- Unique(route_solution_id, version)
- At most one active draft per route_solution
  - PostgreSQL partial unique index on (route_solution_id) where is_active_draft = true

Why this shape:
- Supports iterative drafts
- Preserves audit trail
- Promotion can be atomic and reversible by creating newer drafts

### 4.4 ZoneTemplate small extension for lane seeding

Table: zone_template

Add one new optional column:

- target_route_lanes (Integer, nullable=True)
  - Validation: >= 1 when provided

Semantics:

- Number of initial RouteSolution lanes to seed per zone RouteGroup at plan creation
- Hard upper bound still controlled by max_vehicles when both are set
- Seed count formula:
  - seed_count = min(target_route_lanes or 1, max_vehicles or large_number)

No removal of existing columns required in this phase.

## 5) Command Contract: Draft and Promotion Semantics

### 5.1 Create lane

Command: create_route_solution_lane

Input:
- route_group_id
- optional explicit defaults

Behavior:
- Build defaults from precedence chain:
  1) explicit request fields
  2) zone template route-solution defaults
  3) facility operating hours fallback for set_start/set_end when template window absent
  4) unset
- Create route_solution with lane_status=planned, is_dispatch_target=true
- Auto-create draft version 1 from created lane values (is_active_draft=true)

### 5.2 Save draft

Command: save_route_solution_draft

Input:
- route_solution_id
- patch payload for editable fields
- optional note

Behavior:
- Create new draft row with version = prior_version + 1
- Mark previous active draft false
- New draft becomes active
- Do not mutate route_solution

### 5.3 Promote draft to lane

Command: promote_route_solution_draft

Input:
- route_solution_id
- draft_id
- actor user id

Behavior (single transaction):
- Validate draft belongs to route_solution
- Validate draft completeness rules (vehicle/driver requirements if enforced)
- Copy draft fields into route_solution editable lane fields
- Increment route_solution.version
- Set draft promoted_at and promoted_by_user_id
- Keep draft row immutable after promotion (optional: deactivate it)
- Emit domain event route_solution.promoted

Important:
- Promotion updates one lane only
- Other lanes in same route_group remain unchanged

### 5.4 Seed lanes on plan creation

Command integration: create_plan and create_route_group_in_plan

For each zone route_group created:
- resolve seed_count from template target_route_lanes and max_vehicles
- create seed_count route_solution lanes
- each lane gets deterministic defaults from template helper
- each lane receives an initial draft snapshot

## 6) API Contract (Minimal-Risk Additive)

Phase 1 add endpoints (do not break existing):

- POST /route-groups/{id}/route-solutions
  - Create new lane
- POST /route-solutions/{id}/drafts
  - Save new draft version
- GET /route-solutions/{id}/drafts
  - List draft history
- POST /route-solutions/{id}/promote-draft
  - Promote selected draft

Response additions on route_solution payload:

- lane_status
- lane_index
- is_dispatch_target
- active_draft_id (optional convenience)

Keep old fields including is_selected during migration period.

## 7) Migration Strategy (Low Risk)

### Phase A: Additive schema only

- Add route_solution_draft table
- Add lane_status, lane_index, is_dispatch_target to route_solution
- Add target_route_lanes to zone_template
- No behavior changes yet

### Phase B: Dual-write

- On lane create/update, also create/update drafts
- Keep current route_solution update paths working
- Set is_dispatch_target in sync with current is_selected where needed

### Phase C: Read switch

- UI and services read from draft endpoints for editable state
- Promotion command becomes only path to mutate committed lane configuration

### Phase D: Deprecation cleanup

- Stop using is_selected for lane winner semantics
- Optionally remove dead code paths after observability confirms stability

## 8) Invariants and Validation Rules

- One RouteGroup per (team, plan, zone)
- RouteGroup can have many RouteSolution lanes
- RouteSolution can have many drafts
- Only one active draft per lane
- Promotion must be transactional
- Draft rows are append-only history records (no in-place edits after save)

## 9) Recommendation on Existing ZoneTemplate Fields

- operating_window_start/end: keep as zone policy window override
- default_facility_id: keep as anchor for start location and hours fallback
- max_vehicles: keep as hard cap for lane count
- target_route_lanes (new): desired initial lane seed count
- vehicle_capabilities_required: keep as hard eligibility filter intent
- preferred_vehicle_ids: keep as soft ranking intent
- max_orders_per_route: keep as soft or hard lane sizing cap, configurable by command policy

## 10) Open Decisions to Lock Before Implementation

- Should lane_status transition rules block promotion when status is dispatched? ( yes )
- Should promotion auto-clear assigned orders that no longer fit draft constraints?
- Is max_orders_per_route hard-enforced at assignment time or advisory for optimizer only? ( advisory )
- Should one lane require exactly one vehicle at promote time, or can it remain unassigned? ( required )

## 11) Suggested First Implementation Slice

Deliver this first vertical slice:

1) Add route_solution_draft table
2) Add promote_route_solution_draft command
3) Wire create_route_solution to auto-create draft v1
4) Keep all existing plan creation behavior, just start persisting drafts

This gives immediate user value (safe experimentation) with minimal disruption.
