# Backend Legacy Trace Cleanup Backlog

Date: 2026-03-27
Status: Deferred follow-up backlog

## Purpose
This document tracks the remaining changes required to fully remove legacy naming traces from backend runtime code paths.

Target naming model:
- route_plan
- route_group
- route_plan_id
- route_group_id

Legacy patterns to remove:
- delivery_plan
- local_delivery_plan
- delivery_plan_id (except where intentionally retained for compatibility windows)

## Current Baseline
- Current legacy token count in backend Python: 103
- Scan command used:

```bash
rg -n "delivery_plan|local_delivery_plan" Delivery_app_BK --glob '*.py'
```

## Priority Wave 1 (highest density files)
1. Delivery_app_BK/sockets/emitters/route_solution_events.py
2. Delivery_app_BK/services/infra/events/registry/order.py
3. Delivery_app_BK/services/commands/route_plan/local_delivery/ready_for_delivery.py
4. Delivery_app_BK/services/commands/route_plan/create_plan.py
5. Delivery_app_BK/services/commands/order/update_order.py

Expected work:
- Rename remaining internal variable/function names from legacy terms to route-plan terms.
- Keep API behavior unchanged.
- Preserve any explicit backward-compatibility aliases only when externally required.

## Priority Wave 2 (next cluster)
1. Delivery_app_BK/services/commands/test_data/cleanup.py
2. Delivery_app_BK/services/commands/route_plan/update_plan.py
3. Delivery_app_BK/services/commands/route_plan/local_delivery/route_solution/update_route_solution_from_plan.py
4. Delivery_app_BK/services/commands/order/update_extensions/context_loader.py
5. Delivery_app_BK/services/commands/order/delete_extensions/local_delivery.py
6. Delivery_app_BK/services/commands/order/delete_extensions/context_loader.py
7. Delivery_app_BK/services/commands/local_delivery_app/apply_order_delete_extension.py

Expected work:
- Canonicalize helper names, payload labels, and warning/error text.
- Remove stale legacy fallbacks where canonical keys are already mandatory.

## Priority Wave 3 (infra and messaging cleanup)
1. Delivery_app_BK/sockets/notifications.py
2. Delivery_app_BK/sockets/emitters/route_solution_stop_events.py
3. Delivery_app_BK/sockets/emitters/route_group_events.py
4. Delivery_app_BK/services/infra/events/handlers/order/order_sms.py
5. Delivery_app_BK/services/infra/events/handlers/order/order_email.py
6. Delivery_app_BK/services/infra/events/builders/order/__init__.py
7. Delivery_app_BK/services/infra/events/builders/__init__.py

Expected work:
- Move remaining labels/messages/builders to route-plan wording.
- Keep temporary export aliases only if still used by other modules.

## Priority Wave 4 (test-data and request edge cleanup)
1. Delivery_app_BK/services/commands/test_data/plan_data_creators.py
2. Delivery_app_BK/services/commands/test_data/order_data_creators.py
3. Delivery_app_BK/services/requests/route_plan/plan/local_delivery/update_settings.py
4. Delivery_app_BK/services/commands/route_plan/local_delivery/update_settings.py
5. Delivery_app_BK/services/commands/route_plan/local_delivery/route_solution/plan_sync/incremental_sync.py
6. Delivery_app_BK/services/commands/route_plan/local_delivery/event_helpers.py

Expected work:
- Normalize test payload defaults and helper names to route_plan/route_group.
- Preserve intentional legacy-key rejection tests where explicitly required.

## Definition of Done
For each wave:
1. Apply bounded rename pass in listed files.
2. Run targeted tests for touched modules.
3. Run full suites:
   - `PYTHONPATH=. pytest -q tests/unit/ai`
   - `PYTHONPATH=. pytest -q tests/unit --ignore=tests/unit/ai`
4. Recount tokens and log delta.

Global completion criteria:
- Legacy token scan in backend Python reaches near-zero except approved compatibility aliases.
- No runtime regressions in unit suites.
- Runbook remains canonical and up to date.

## Guardrails
- Do not remove compatibility aliases that are still consumed externally without coordinated contract migration.
- Avoid broad mechanical replacements without bounded test validation.
- Keep changes in small waves to simplify rollback and review.
