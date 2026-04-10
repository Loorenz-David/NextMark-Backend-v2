# Implementation Context Snapshot (Backend)

## Date
- 2026-03-04

## Purpose
This file captures backend implementation context across Costumer, Order, Delivery Windows, Optimizer, and Directions warning flows so work can resume safely after unrelated refactors.

## High-Level Scope Implemented
1. Costumer service/request/query architecture and API v2 router foundation.
2. Order-create costumer association flow with resolve-or-create behavior.
3. Costumer update operating-hours replacement hardening.
4. Delivery Windows v3 domain rules in order create/update + serialization + optimizer usage.
5. Centralized time-window warning evaluation in directions/route local-plan update paths.

## Costumer + Order Association Context
1. `create_order` supports costumer association resolution path (explicit `costumer_id` and fallback resolve/create behavior).
2. Batch-safe resolver approach is used to avoid per-order query loops where possible.
3. Conflict preference in fallback matching uses email before phone.
4. Order serializers include `costumer_id` for response visibility.

## Costumer Query/Flow Notes
1. `find_costumers` supports querying specific columns when keys besides `q` are supplied (pattern aligned with order-query behavior).
2. Costumer normalization responsibilities were moved toward domain-oriented placement where requested.

## Costumer Update Operating Hours Stability
1. `replace_operating_hours=true` path was hardened to avoid `(costumer_id, weekday)` unique conflicts.
2. Replacement flow ensures deterministic delete-before-reinsert behavior so overlapping old/new weekdays do not trigger insert uniqueness failures.
3. Current frontend edit payload with `replace_operating_hours` is supported.

## Delivery Windows v3 Backend Rules (Authoritative)
1. UTC-only transport/storage policy:
   - reject naive datetimes
   - reject non-UTC offsets
2. Interval semantics are half-open for overlap checks:
   - overlap invalid when `next.start_at < prev.end_at`
   - adjacency (`==`) is valid
3. Strict duration:
   - `end_at > start_at`
4. Max windows:
   - 14 per order
5. Same-day validation:
   - each window must remain within one local calendar day after UTC -> team-timezone conversion
6. Multiple windows per local day are allowed if non-overlapping.
7. PATCH semantics:
   - `delivery_windows` absent => no change
   - `delivery_windows: []` => explicit clear
8. Legacy envelope derivation:
   - earliest/latest derived from min/max window bounds
   - preferred HH:mm only when all windows share same local pair

## Delivery Windows Domain Module
1. `services/domain/order/delivery_windows.py` is the validation/normalization core for:
   - timezone resolution
   - strict UTC validation
   - max-count checks
   - sorting
   - non-overlap checks
   - same-local-day checks
   - legacy envelope derivation

## Order Create/Update Integration
1. `create_order` validates/normalizes incoming `delivery_windows`, applies same-local-day checks, persists rows, and derives legacy fields.
2. `update_order` supports atomic replace semantics when `delivery_windows` key is present.
3. Empty-list replace clears windows and nulls derived legacy envelope fields.

## Serializer / Query Context
1. Order serializers include `delivery_windows` and return them sorted by `start_at ASC` (UTC canonical ordering).
2. `costumer_id` is included in order serialization outputs for create/list/get/update paths using shared serializers.

## Optimizer Integration Context
1. Optimizer request builder loads and uses `order.delivery_windows` as authoritative constraints when present.
2. Legacy earliest/latest/preferred logic is fallback-only when no delivery windows exist.
3. Orders are loaded with `selectinload(Order.delivery_windows)` to avoid N+1 behavior.

## Directions / Route Local-Plan Time-Window Centralization
1. New centralized policy module:
   - `Delivery_app_BK/directions/services/time_window_policy.py`
2. Central module responsibilities:
   - resolve effective windows per stop/order (`delivery_windows` first, then legacy fallback)
   - evaluate arrivals against windows
   - apply/clear `time_window_violation` warning consistently
   - preserve non-time warnings while replacing only time-window warnings
   - apply consistent skip-reason behavior for outside-window states
3. Rewired paths now using centralized logic:
   - directions refresher
   - local-delivery order update extension warning recompute
   - route solution plan-sync time-window update path
4. `directions/services/warnings.py` is now a compatibility wrapper to centralized policy.

## Entry Points Covered by Centralized Warning Logic
1. Stop reorder flow:
   - `services/commands/plan/local_delivery/route_solution/stops/update_route_stop_position.py`
   - via incremental refresh -> centralized warning application
2. Plan change flow:
   - `services/commands/order/plan_changes/local_delivery.py`
   - via incremental sync action path
3. Plan objective flow:
   - `services/commands/order/plan_objectives/local_delivery.py`
   - via incremental sync action path
4. Order update extension flow:
   - `services/commands/order/update_extensions/local_delivery.py`
   - direct warning recompute now centralized

## Tests Run for Centralization Work
Executed with backend venv:
- `PYTHONPATH=. .venv/bin/pytest ...`

Targeted suites passed:
1. `tests/unit/directions/test_refresher_stop_warnings.py`
2. `tests/unit/services/commands/plan/local_delivery/route_solution/plan_sync/test_stop_window_updates.py`
3. `tests/unit/services/commands/plan/local_delivery/route_solution/test_update_route_solution_from_plan.py`
4. `tests/unit/services/commands/order/plan_objectives/test_local_delivery_bundle_sync.py`
5. `tests/unit/services/commands/order/plan_changes/test_local_delivery_plan_change_bundle_sync.py`
6. `tests/unit/directions/test_time_window_policy.py` (new)

Result at checkpoint:
- 17 passed

## Known Follow-Ups
1. Add dedicated tests for `handle_local_delivery_order_update_extension` warning recompute path (direct unit coverage).
2. Optional cleanup pass to remove now-dead legacy window-warning helper branches once stable.
3. DB hardening follow-up for `order.costumer_id` non-null migration remains a separate task.

