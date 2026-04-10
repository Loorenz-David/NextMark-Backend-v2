# Route Operations Refactor Context

Last updated: 2026-03-26
Owner: Delivery backend refactor stream
Status: In progress (Phase 1 models completed, Phase 2 structure regrouping completed)

## Phase 2 Structure Update (Completed)
This pass was intentionally folder-structure only.

### API v2 router regrouping
- Delivery-plan chain routers are now nested under `Delivery_app_BK/routers/api_v2/delivery_plan/`:
  - `plan.py`
  - `local_delivery_plans.py`
  - `store_pickup_plans.py`
  - `international_shipping_plans.py`
  - `plan_overviews.py`
  - `route_operations.py`
  - `route_solution.py` (kept as legacy/auxiliary file)
- Blueprint registration in `routers/api_v2/__init__.py` was rewired to import from this package.
- URL prefixes were kept unchanged (no API contract changes in this pass).

### Service regrouping under delivery_plan namespace
- Commands moved from `services/commands/plan/` to `services/commands/delivery_plan/`.
- Queries moved from `services/queries/plan/` to `services/queries/delivery_plan/`.
- Plan state and type query packages are now grouped under:
  - `services/queries/delivery_plan/plan_states/`
  - `services/queries/delivery_plan/plan_types/`
- Domain modules were grouped under:
  - `services/domain/delivery_plan/plan/`
  - `services/domain/delivery_plan/local_delivery/`
  - `services/domain/delivery_plan/route_solution/`
- Request modules were grouped under:
  - `services/requests/delivery_plan/plan/`
  - `services/requests/delivery_plan/local_delivery/`
- Import paths were rewired across the codebase to the new package locations.

### Boundary confirmation
- Order remains independent and was not moved under route_operations or delivery_plan model domains.

## Purpose
This file is the running context log for the route-operations refactor.
Future Copilot sessions should read this first to understand what changed, what is canonical now, and what remains.

## Scope of Current Change Set
This phase started the model-domain relabel from delivery-plan naming to route-operations naming.

### Primary domain rename intent
- DeliveryPlan -> RoutePlan
- LocalDeliveryPlan -> RouteGroup
- Keep Order class/table name as Order/order and keep it independent under `models/tables/order/`
- Shared state catalog remains the same table (`plan_state`) for now
- Date strategy added on RoutePlan with values: `single`, `range`

## Canonical Model Paths (Use These Going Forward)
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_plan.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_group.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_solution.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_stop.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_plan_state.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_plan_event.py`
- `Delivery_app_BK/models/tables/route_operations/route_plan/route_plan_event_action.py`
- `Delivery_app_BK/models/tables/order/order.py`

## Central Model Export Cutover
`Delivery_app_BK/models/__init__.py` now exports route-operations model classes from the new paths.

## Compatibility Bridge (Temporary)
Old modules under `models/tables/delivery_plan/*` were converted to thin re-export wrappers.

Reason:
- Prevent immediate mapper/import breakage while service/query/router layers are still being rewired in Phase 2.

Important:
- This is temporary compatibility inside the codebase, not API backward compatibility.
- Once service wiring is complete, these wrappers should be removed.

## Data Contract Changes Implemented in Models
### RoutePlan
- `plan_type` removed from canonical RoutePlan model.
- `date_strategy` added (`single|range`).
- Date normalization behavior added:
  - `start_date` normalized to start of day.
  - `end_date` normalized to end of day.
  - Accepts ISO datetime strings and `YYYY-MM-DD` values.
  - `single` strategy auto-aligns end date to same-day end.

### RouteGroup
- Added totals columns:
  - `total_weight_g`
  - `total_volume_cm3`
  - `total_item_count`
  - `total_orders`
- Added `state_id` -> shared `plan_state` FK.

### Relationship relabels
- `order.delivery_plan_id` -> `order.route_plan_id`
- `route_solution.local_delivery_plan_id` -> `route_solution.route_group_id`
- RoutePlan no longer owns direct relationships to international_shipping/store_pickup models.

## Migration File Added
- `migrations/versions/rc1p1m0d3l99_route_operations_phase1_models.py`

Intent of this migration:
- Rename tables/columns toward RoutePlan/RouteGroup naming
- Add `date_strategy`
- Add RouteGroup totals and state linkage

Note:
- Migration execution still needs full project validation in environment-specific Alembic setup.

## How to Use the System Now (Developer Guidance)
1. New route-plan model work must import from `models/tables/route_operations/route_plan/*` paths.
2. Order model imports must use `models/tables/order/order.py`.
3. New service/query code should treat `RoutePlan` and `RouteGroup` as canonical concepts.
4. Avoid introducing new code that depends on old `delivery_plan` model paths.
5. If touching old wrappers, treat them as transitional and keep logic in canonical files only.

## Next Planned Refactor Step
Phase 2: Service/query/router relabel and relink
- Replace DeliveryPlan/LocalDeliveryPlan naming in services with RoutePlan/RouteGroup
- Rewire FK field usage in request/command/query layers (`delivery_plan_id` -> `route_plan_id`, etc.)
- Update route operations and assignment services to canonical model naming
- Remove wrapper dependencies once references are fully migrated

## Open Decisions / Watchouts
- Shared state table semantics are intentionally reused for now; meaning differs by context.
- Team/user backrefs were renamed where needed (example: `route_groups`), verify all consumers.
- Keep monitoring for residual direct imports to old module paths during Phase 2.

## Session Continuation Checklist
For the next Copilot session:
1. Read this file.
2. Search for `DeliveryPlan`, `LocalDeliveryPlan`, `delivery_plan_id`, `local_delivery_plan_id` in services/queries/routers.
3. Rewire in bounded slices and run diagnostics after each slice.
4. Remove transitional wrappers only after zero remaining old-path dependencies.
