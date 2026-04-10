# Route Architecture Migration Handoff

Date: 2026-03-26
Repository: Back_end
Scope: route_plan and route_group migration from legacy delivery_plan and local_delivery_plan naming

## Refactor Goal

Move backend architecture and contracts from legacy naming:
- delivery_plan
- local_delivery_plan

to canonical naming:
- route_plan
- route_group
- route_operations

while preserving system stability during transition.

## What It Was

Previous state used mixed and legacy-first naming across:
- routers and URL prefixes
- order request and serialization payloads
- sockets and notifications
- route optimization and directions contexts
- extension loaders and plan-change logic

Core legacy public API examples:
- /api_v2/plans
- /api_v2/local_delivery_plans
- /api_v2/plan_overviews

## What It Has Become

Current state is canonical-first in several critical layers:
- API v2 router prefixes migrated to route_plans and route_groups
- route_operations already canonical and retained
- many order workflows now canonical internally with compatibility handling
- route-group context aliases in plan-change and objective paths
- objective workspace labeling bridge added for route_operations

Current canonical API map is documented in:
- Delivery_app_BK/routers/api_v2/delivery_plan/ROUTE_API_MIGRATION_MAP.md

## Completed Work

### 1) Router Surface Migration

Public prefixes migrated:
- /api_v2/plans -> /api_v2/route_plans
- /api_v2/local_delivery_plans -> /api_v2/route_groups
- /api_v2/plan_overviews -> /api_v2/route_plan_overviews

Files:
- Delivery_app_BK/routers/api_v2/__init__.py
- Delivery_app_BK/routers/api_v2/delivery_plan/plan.py
- Delivery_app_BK/routers/api_v2/delivery_plan/local_delivery_plans.py
- Delivery_app_BK/routers/api_v2/delivery_plan/plan_overviews.py

### 2) New Router Scaffold Added

New endpoint scaffolded for frontend development:
- GET /api_v2/route_plans/:routePlanId/route_groups/

Status:
- Router exists
- Service integration pending
- Temporary response returns empty route_group list with warning

File:
- Delivery_app_BK/routers/api_v2/delivery_plan/plan.py

### 3) Canonical Query Namespace Adoption

Canonical route_plan query usage is in place for main plan flows.

Files include:
- Delivery_app_BK/services/queries/route_plan/list_route_plans.py
- Delivery_app_BK/services/queries/route_plan/get_route_plan.py
- Delivery_app_BK/services/queries/route_plan/plan_states/list_route_plan_states.py
- Delivery_app_BK/services/queries/route_plan/plan_types/get_route_group_plan_type.py

### 4) Order Request and Serialization Migration Slices

Implemented:
- route_plan_id alias support in order create request
- route_plan_id support in CSV import path
- canonical route_plan_id output in serializers with legacy alias preserved
- route_plan_id alias support in batch selection parser

Files include:
- Delivery_app_BK/services/requests/order/create_order.py
- Delivery_app_BK/services/commands/order/create_order_import.py
- Delivery_app_BK/services/queries/order/serialize_order.py
- Delivery_app_BK/services/requests/order/update_orders_delivery_plan_batch.py

### 5) Order Commands Canonicalization (Partial)

Implemented canonical internal naming and compatibility helpers in:
- create_order
- update_order
- update_order_delivery_plan
- plan objectives orchestrator/local_delivery
- plan changes orchestrator/local_delivery/types

Files include:
- Delivery_app_BK/services/commands/order/create_order.py
- Delivery_app_BK/services/commands/order/update_order.py
- Delivery_app_BK/services/commands/order/update_order_delivery_plan.py
- Delivery_app_BK/services/commands/order/plan_objectives/orchestrator.py
- Delivery_app_BK/services/commands/order/plan_objectives/local_delivery.py
- Delivery_app_BK/services/commands/order/plan_changes/orchestrator.py
- Delivery_app_BK/services/commands/order/plan_changes/local_delivery.py
- Delivery_app_BK/services/commands/order/plan_changes/types.py

### 6) Objective Label Bridge (Important)

Order plan objective remains persisted under existing business values:
- local_delivery
- international_shipping
- store_pickup

Added compatibility and canonical workspace mapping:
- Accept input aliases route_operation and route_operations
- Normalize to local_delivery for persistence and existing validators
- Expose order_plan_workspace for canonical frontend workspace routing

Files:
- Delivery_app_BK/services/domain/order/plan_objective_labels.py
- Delivery_app_BK/models/tables/order/order.py
- Delivery_app_BK/services/requests/order/create_order.py
- Delivery_app_BK/services/commands/order/create_serializers.py
- Delivery_app_BK/services/queries/order/serialize_order.py
- Delivery_app_BK/services/infra/events/builders/order/order_events.py

## Current In Progress

1) Compatibility mode remains active.
- Canonical behavior is primary in many paths.
- Legacy aliases and wrappers still exist in many runtime modules.

2) Some subsystems still carry legacy-heavy naming.
- sockets and notifications
- route optimization loaders/builders
- directions and execution paths
- AI prompts/contracts

3) Router scaffold endpoint is not service-backed yet.
- GET /api_v2/route_plans/:routePlanId/route_groups/

## Missing Work

### A) Service Wiring for New Endpoint

Implement and connect service/query for:
- GET /api_v2/route_plans/:routePlanId/route_groups/

Expected output should include the route groups attached to a route plan.

### B) Payload Contract Completion

Continue canonical-first payload migration in:
- sockets emitters
- notifications
- optimization query/serialization payloads

Keep compatibility only where needed.

### C) Prompt and Tool Contract Alignment

Update AI prompt docs and tool contracts to include canonical naming where appropriate, while preserving operational behavior.

### D) Wrapper Retirement Phase (Later)

Retire legacy wrappers only after:
- zero callsites
- frontend switched
- regression tests green

## Next Steps Planned (for next agent)

1) Implement service wiring for route plan -> route groups endpoint.
- Router already exists.
- Add query service and hook to router.
- Add unit tests for success, no route groups, and plan not found/team scope behavior.

2) Normalize route group payload contracts in sockets and notifications.
- Ensure canonical keys are present and primary.
- Keep temporary legacy mirror keys only if consumers still require them.

3) Continue runtime canonicalization in remaining order and optimization hotspots.
- Prioritize high-traffic modules first.

4) Refresh migration report and tests after each batch.
- Run focused pytest suites for touched areas.
- Run scripts/report_route_naming_legacy_refs.py and track trend.

## Useful Artifacts for Continuation

- Endpoint mapping for frontend:
  - Delivery_app_BK/routers/api_v2/delivery_plan/ROUTE_API_MIGRATION_MAP.md

- Migration runbook and metrics script:
  - docs/runbooks/route_naming_migration.md
  - scripts/report_route_naming_legacy_refs.py

## Notes for Handoff

- This branch/worktree has multiple modified files across routers, order commands, requests, and tests.
- Avoid reverting unrelated changes.
- Continue with small safe batches and focused tests.
- The highest-value immediate feature gap is service integration for the new route_groups listing endpoint under route_plans.
