# Zones Route Plan Integration — Completion Record

Created: 2026-03-27 14:45:36 CET
Status: Implemented
Scope: Backend only (AI explicitly out of scope)
Source plan: `docs/under_development/ZONES_ROUTE_PLAN_INTEGRATION_GAPS.md`

## Completion Decision
The plan is complete for backend scope and can be archived.

## Implemented Gaps

1. GAP 2 completed
- Added `route_groups_count` to plan serialization.
- Added detail-only inline `route_groups` summary on single-plan response.
- Added eager loading for route groups in list/detail plan queries.

2. GAP 1 completed
- `create_plan` no longer creates a ghost zone-less route group by default.
- Added optional `zone_ids` support to create-plan request parsing.
- Added zone-aware route-group and route-solution creation path when `zone_ids` is provided.
- Create-plan response now supports `route_groups` and `route_solutions` bundles for zone-aware creation.

3. GAP 4 completed
- Added domain function `recompute_route_group_totals(plan)`.
- Reused it from route-group materialization.
- Wired recompute into order-plan membership mutation flows.
- Wired recompute into zone reassignment background job for affected plans.

## Validation
Focused tests executed and passing:
- `tests/unit/services/queries/route_plan/test_response_contracts.py`
- `tests/unit/services/queries/route_plan/test_serialize_plan.py`
- `tests/unit/services/commands/plan/test_materialize_route_groups.py`
- `tests/unit/services/commands/plan/test_create_plan_zones.py`
- `tests/unit/services/domain/plan/test_recompute_route_group_totals.py`

Result: `12 passed`.

## Archive Action
The source planning file should be moved to archive as a completed handoff artifact.
