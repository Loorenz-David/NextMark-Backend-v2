# Architecture Overview

## Core runtime pieces
- Flask app (`Delivery_app_BK`) for HTTP APIs and Socket.IO.
- SQLAlchemy models for relational state.
- Alembic migrations under `migrations/`.
- Redis + RQ workers for async processing and event relay.

## Main backend layers
- `routers/`: request/response and auth decorators.
- `services/commands/`: write operations.
- `services/queries/`: read operations.
- `services/domain/`: reusable business rules and state engines.
- `models/`: table mappings and data-level helpers.
- `sockets/`: realtime emitters and handlers.

## Delivery plan state flow (high-level)
- Plan state and order state transitions are handled by command flows plus domain state engines.
- Route-solution counters (`order_count`, `order_state_counts`) are recomputed after relevant mutations.
- Auto-complete decisions are made from selected route solution counters.

For full behavior matrix, see [State Transitions](state-transitions.md).
