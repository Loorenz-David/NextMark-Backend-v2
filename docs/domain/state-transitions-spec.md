# State Transitions Logic

This document explains the current route plan and order state transition rules implemented in the backend.

## State IDs

### Plan states
- OPEN: 1
- READY: 2
- PROCESSING: 3
- COMPLETED: 4
- FAIL: 5

### Order states (relevant here)
- CONFIRMED
- READY
- PROCESSING
- COMPLETED
- FAIL
- CANCELLED

## Core modules

- `Delivery_app_BK/services/domain/state_transitions/order_count_engine.py`
  - Recomputes per-route counts (`order_count`) and per-state distribution (`order_state_counts`).
- `Delivery_app_BK/services/domain/state_transitions/plan_state_engine.py`
  - Plan-level state helpers (`apply_plan_state`, `maybe_auto_complete_plan`, etc.).
- `Delivery_app_BK/services/domain/state_transitions/order_move_rules.py`
  - Pure matrix function for order/plan state behavior when an order is moved between plans.

## Auto-complete rule

Implemented in `maybe_auto_complete_plan(plan)`:
- Applies only to `local_delivery` plans.
- Uses the selected route solution.
- If `order_count > 0` and `Completed >= order_count`, the plan is transitioned to `COMPLETED`.
- This now works even if the plan never transitioned through `PROCESSING`.

Why this matters:
- Admins can manually set all orders to `COMPLETED` while plan is still `OPEN` or `READY`, and the plan can still auto-complete.

## Reset-to-open rule

Implemented during settings updates:
- If plan window or route config changes and plan is not already `OPEN`, plan is reset to `OPEN`.

Reason:
- Route assumptions changed; previous operational state may no longer be valid.

## Driver start rule

When driver marks route actual start time:
- Plan transitions to `PROCESSING`.

## Ready-for-delivery rule

When plan is marked READY:
- Plan transitions to `READY`.
- Orders in terminal states (`COMPLETED`, `CANCELLED`) are excluded from bulk order-state update.

## Order move matrix (destination plan)

### Destination plan = COMPLETED
- Order COMPLETED: no change
- Order not COMPLETED and destination plan end is in the past: order -> COMPLETED
- Order not COMPLETED and destination plan end is not in the past: plan -> PROCESSING

### Destination plan = PROCESSING
- Any order state: order -> PROCESSING

### Destination plan = OPEN
- Order COMPLETED: order -> CONFIRMED
- Order PROCESSING: order -> CONFIRMED
- Other states: no change

### Destination plan = READY
- Order READY: no change
- Order PROCESSING: order -> FAIL, plan -> OPEN, create case
- Other states: plan -> OPEN

### Destination plan = FAIL (or unknown)
- No automatic changes

## Case creation behavior

On READY + PROCESSING move case:
- System creates an `OrderCase` (state `OPEN`)
- Adds `CaseChat` with predefined explanation
- Appends optional user message if provided in request payload (`case_message`)

## Data integrity and recomputation flow

After operations that can change order distribution (create/delete/state-change/plan-move):
1. Recompute plan totals
2. Recompute per-state order counts
3. Apply move-state heritage (where applicable)
4. Recompute counts again if states changed by move matrix
5. Evaluate auto-complete transition

## Practical examples

- Example A: Admin marks all orders completed while plan is OPEN
  - Counts become all completed
  - Auto-complete rule sets plan to COMPLETED

- Example B: Move PROCESSING order into OPEN plan
  - Order transitions to CONFIRMED

- Example C: Move PROCESSING order into READY plan
  - Order transitions to FAIL
  - Plan resets to OPEN
  - Case is created for traceability
