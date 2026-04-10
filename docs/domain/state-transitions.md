# State Transitions

This page summarizes current route plan and order transition behavior.

## Sources of truth
- Domain engines:
  - `Delivery_app_BK/services/domain/state_transitions/plan_state_engine.py`
  - `Delivery_app_BK/services/domain/state_transitions/order_move_rules.py`
  - `Delivery_app_BK/services/domain/state_transitions/order_count_engine.py`
- Detailed spec:
  - [State transition spec](state-transitions-spec.md)

## Key behavior
- Plan can auto-complete when all selected-route orders are completed.
- This auto-complete is allowed even when a plan never entered PROCESSING.
- When moving an order into an OPEN plan:
  - COMPLETED order -> CONFIRMED
  - PROCESSING order -> CONFIRMED
- READY-plan edge case for moved PROCESSING order:
  - order -> FAIL
  - plan -> OPEN
  - case is created for traceability
