# Real-Time Event System Architecture

**Last Updated**: March 18, 2026  
**Status**: Production Ready  
**Phases Completed**: 1, 1.5, 2 (Core Infrastructure, Emitters, Command Wire-Up)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Event Pipeline](#event-pipeline)
3. [Event Models & Tables](#event-models--tables)
4. [Event Types & Broadcasting](#event-types--broadcasting)
5. [Database Cleanup & TTL](#database-cleanup--ttl)
6. [Logging & Debugging](#logging--debugging)
7. [Authorization & Security](#authorization--security)
8. [Testing & Monitoring](#testing--monitoring)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

The real-time system enables **instant synchronization** of delivery operations across:
- **Admin App** → See all orders, routes, and route plans in real-time
- **Driver App** → See assigned routes and order updates instantly
- **Backend** → Emits events when business logic changes

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    REST API Command                         │
│  e.g., PUT /routes/{id}/solution (assign driver)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Command Layer (update_route_solution_fields)        │
│  Updates route_solution.driver_id                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│    Event Creation (event_helpers.py)                        │
│  create_route_solution_event(...)                           │
│  → RouteSolutionEvent table (status=PENDING)                │
└──────────────────────┬──────────────────────────────────────┘
                       │ 1-3 seconds
                       ▼
┌─────────────────────────────────────────────────────────────┐
│    Redis Dispatcher (redis_dispatcher.py)                   │
│  Polls every 1-3 seconds for PENDING events                 │
│  Marks as CLAIMED + enqueues to RQ "events" queue           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│    RQ Worker (events queue)                                 │
│  Processes job: relay_route_solution_event_job(event_id)    │
│  Fetches entity from DB + calls emit function               │
│  Marks event as DISPATCHED                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│    Socket.IO Emitter (route_solution_events.py)             │
│  emit_route_solution_updated(...) calls                     │
│  socketio.emit(..., room=team_orders + team_members)        │
│  Marks event relayed_at = now (idempotency)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│    Connected Clients (Socket.IO)                            │
│  Admin App: Receives in team_orders room                    │
│  Driver App: Receives in team_members room (if authorized)  │
│  Frontend state updates + UI refreshes                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Event Pipeline

### Step 1: Event Creation (In Command)

**File**: `services/commands/plan/local_delivery/event_helpers.py`

When a command changes state that needs to be broadcast:

```python
from Delivery_app_BK.services.commands.plan.local_delivery.event_helpers import (
    create_route_solution_event
)

def update_route_solution_fields(ctx, route_solution_id, driver_id=None, ...):
    route_solution = db.session.get(RouteSolution, route_solution_id)
    
    # Business logic: update driver
    old_driver_id = route_solution.driver_id
    if driver_id is not None:
        route_solution.driver_id = driver_id
    
    db.session.commit()
    
    # Emit event if something changed
    if driver_id is not None and driver_id != old_driver_id:
        create_route_solution_event(
            ctx=ctx,
            team_id=route_solution.team_id,
            route_solution_id=route_solution.id,
            event_name="route_solution.updated",
            payload={
                "driver_id": driver_id,
                "previous_driver_id": old_driver_id,
            }
        )
```

**Returns**: `RouteSolutionEvent` instance or `None` if `ctx.prevent_event_bus=True`

---

### Step 2: Dispatcher Claims & Enqueues

**File**: `services/infra/events/dispatcher.py`

Runs continuously via `redis_dispatcher.py`:

```python
def dispatch_pending_events(dispatcher_id, batch_size=50, lease_seconds=120):
    for target in DISPATCH_TARGETS:  # All 6 event types
        # 1. Query pending events
        claimed_rows = _claim_rows(
            target, 
            dispatcher_id=dispatcher_id,
            batch_size=batch_size
        )
        
        # 2. For each event, enqueue to RQ
        for row in claimed_rows:
            enqueue_job(
                queue_key="events",
                fn=target.job_fn,  # e.g., relay_route_solution_event_job
                args=(row.id,),
                ...
            )
            row.dispatch_status = "DISPATCHED"
```

**Key Features**:
- Claims with `FOR UPDATE SKIP LOCKED` (no duplicate processing)
- Repairs stale claims (if worker crashes)
- Retry backoff: 15, 30, 45... seconds up to 5 minutes
- Max attempts: 5 (then marked DEAD for investigation)

---

### Step 3: RQ Worker Relays to Socket.IO

**File**: `services/infra/jobs/tasks/realtime.py`

Worker processes the RQ job:

```python
@with_app_context
def relay_route_solution_event_job(event_row_id: int) -> None:
    event_row = db.session.get(RouteSolutionEvent, event_row_id)
    if event_row is None:
        current_app.logger.warning("Event not found: %d", event_row_id)
        return
    
    # Idempotency: skip if already relayed
    if event_row.relayed_at is not None:
        current_app.logger.debug("Event already relayed: %d", event_row_id)
        return
    
    try:
        # Fetch entity + emit
        route_solution = db.session.get(RouteSolution, event_row.route_solution_id)
        if route_solution is None:
            return
        
        if event_row.event_name == "route_solution.created":
            emit_route_solution_created(route_solution, payload=event_row.payload)
        elif event_row.event_name == "route_solution.updated":
            emit_route_solution_updated(route_solution, payload=event_row.payload)
        # ... etc
        
        # Mark as relayed for idempotency on retry
        event_row.relayed_at = datetime.now(timezone.utc)
        db.session.commit()
        
    except Exception as exc:
        current_app.logger.error("Failed to relay: %s", str(exc), exc_info=True)
        raise  # RQ will retry
```

---

### Step 4: Socket.IO Emit to Connected Clients

**File**: `sockets/emitters/route_solution_events.py`

```python
def emit_route_solution_updated(route_solution, payload=None):
    envelope = build_business_event_envelope(
        event_name="route_solution.updated",
        team_id=route_solution.team_id,
        entity_type="route_solution",
        entity_id=route_solution.id,
        payload={
            "route_solution_id": route_solution.id,
            "driver_id": route_solution.driver_id,
            "expected_start_time": ...,
            ...
        }
    )
    
    # Broadcast to admin room
    emit_business_event(
        room=build_team_orders_room(team_id),
        envelope=envelope
    )
    
    # Broadcast to driver notification room
    emit_business_event(
        room=build_team_members_room(team_id),
        envelope=envelope
    )
```

**Socket.IO Contract** (broadcasted to clients):
```json
{
    "event_id": "uuid-...",
    "event_name": "route_solution.updated",
    "version": "1.0",
    "occurred_at": "2025-03-18T12:30:00Z",
    "team_id": 123,
    "entity_type": "route_solution",
    "entity_id": 456,
    "app_scopes": ["admin", "driver"],
    "payload": {
        "route_solution_id": 456,
        "driver_id": 789,
        "expected_start_time": "2025-03-18T14:00:00Z",
        ...
    }
}
```

---

## Event Models & Tables

### Database Schema

All event tables inherit from `DispatchStateMixin`:

```python
class DispatchStateMixin:
    # Identification
    event_id: str (unique, index)
    entity_type: str (e.g., "route_solution")
    entity_id: int (e.g., 456)
    entity_version: str (for optimistic locking)
    
    # Event metadata
    team_id: int (foreign key)
    actor_id: int (user who triggered, foreign key)
    occurred_at: datetime (index) ← When event occurred
    
    # Dispatch state machine
    dispatch_status: str (enum: PENDING, CLAIMED, DISPATCHED, FAILED, DEAD) (index)
    dispatch_attempts: int (retry count)
    claimed_by: str (dispatcher ID that claimed it)
    claimed_at: datetime (when dispatcher claimed it)
    next_attempt_at: datetime (exponential backoff schedule)
    last_error: str (error message from last attempt)
    
    # Relay/idempotency
    relayed_at: datetime (null until Socket.IO emit succeeds) (index)
```

### Event Tables

| Table | Models | Purpose | Created By |
|-------|--------|---------|-----------|
| `order_event` | OrderEvent | Order CRUD events | Order commands |
| `route_plan_event` | RoutePlanEvent | Route plan reschedule | Plan commands |
| `route_group_event` | RouteGroupEvent | Route group updates | Route group commands |
| `route_solution_event` | RouteSolutionEvent | Route solutions (create/update/delete/select) | Route commands |
| `route_solution_stop_event` | RouteSolutionStopEvent | Route stops (position/timing) | Route commands |
| `app_event_outbox` | AppEventOutbox | App-level events (for orders) | App commands |

---

## Event Types & Broadcasting

### Route Solution Events (Phase 2)

**When Emitted**:
- `route_solution.created` - New route solution created
- `route_solution.updated` - Route solution changed (driver, timing, selection)
- `route_solution.deleted` - Route solution deleted
- `route_solution.selected` - Route marked as selected for execution

**Broadcast Rooms**:
- `team_orders:{team_id}` → Admin app (all routes visible)
- `team_members:{team_id}` → Drivers (notification of routing changes)

**Example Payload**:
```json
{
    "route_solution_id": 456,
    "route_group_id": 789,
    "label": "Route A - Morning",
    "is_selected": true,
    "driver_id": 999,
    "expected_start_time": "2025-03-18T14:00:00Z",
    "expected_end_time": "2025-03-18T18:00:00Z"
}
```

### Route Solution Stop Events

**When Emitted**:
- `route_solution_stop.updated` - Stop position, sequence, or timing changed

**Broadcast Rooms**:
- `team_orders:{team_id}` → Admin app
- `route_orders:{team_id}:{route_id}` → Driver assigned to route

**Example Payload**:
```json
{
    "route_solution_stop_id": 111,
    "route_solution_id": 456,
    "sequence": 5,
    "service_time_minutes": 15,
    "arrival_time": "2025-03-18T15:30:00Z",
    "departure_time": "2025-03-18T15:45:00Z"
}
```

### Route Group Events

**When Emitted**:
- `route_group.updated` - Route group settings changed (driver assignment, dates)

**Broadcast Room**:
- `team_orders:{team_id}` → Admin app

---

## Database Cleanup & TTL

### Event Table Growth

Event tables grow continuously (1000s per day in high-volume operations). Without cleanup:
- Tables grow unbounded
- Queries slow down (especially on `occurred_at` index)
- Storage costs increase

### Cleanup Service

**File**: `services/infra/events/cleanup.py`

```python
def cleanup_old_events(retention_days=30) -> dict:
    """Delete events older than retention_days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    for model in [OrderEvent, RouteSolutionEvent, ...]:
        deleted = db.session.query(model).filter(
            model.occurred_at < cutoff_date
        ).delete(synchronize_session=False)
```

### Usage

```bash
# Check stats before cleanup
python event_cleanup_manager.py stats

# Delete events older than 30 days
python event_cleanup_manager.py cleanup --retention-days 30

# View results
python event_cleanup_manager.py stats
```

### Recommended Schedule

```cron
# Weekly cleanup (Sunday 2 AM)
0 2 * * 0 cd /app && python event_cleanup_manager.py cleanup --retention-days 30
```

---

## Logging & Debugging

### Log Levels

| Level | When | Example |
|-------|------|---------|
| DEBUG | Normal operation (verbose) | "Event already relayed (idempotency): 123" |
| INFO | Milestones | "Emitted route_solution.updated: solution_id=456, team_id=789" |
| WARNING | Missing references (non-blocking) | "RouteGroup not found for event 123" |
| ERROR | Failures (will retry) | "Failed to relay RouteSolutionEvent 456: network timeout" |
| CRITICAL | System down (needs investigation) | "Dispatcher loop failed: Redis connection error" |

### Trace Event Flow

To follow a specific event through the system:

```bash
# 1. Find event ID in logs
grep "route_solution.updated" app.log | grep "solution_id=456"
# Output: [INFO] Emitted route_solution.updated: solution_id=456, team_id=789, event_id=abc-123

# 2. Trace through dispatcher
grep "abc-123" app.log | grep dispatcher
# Output: [INFO] Cleaned up 50 old route_solution_events

# 3. Check relay logs
grep "abc-123" app.log | grep relay
# Output: [DEBUG] Event relayed successfully: 123

# 4. Monitor Socket.IO
# Frontend receives event in its console logs
```

### Common Log Patterns

**Normal flow**:
```
[INFO] Created RouteSolutionEvent: id=123, event_name=route_solution.updated, team_id=789
[INFO] Cleaned up route_solution_events (before 2025-02-16T12:00:00Z), attempts=1, next_attempt_at=2025-03-18T12:00:03Z
[DEBUG] Event relayed successfully: 123
[INFO] Emitted route_solution.updated: solution_id=456, team_id=789
```

**Retry flow** (RQ worker failed, dispatcher retries):
```
[ERROR] Failed to relay RouteSolutionEvent 123: ConnectionError (dispatcher=abc, attempts=1)
[INFO] Claimed row updated: dispatch_status=PENDING, next_attempt_at=2025-03-18T12:00:18Z
[NEXT CYCLE - 15 seconds later]
[INFO] Claimed event for retry: id=123, dispatch_status=CLAIMED
[DEBUG] Event relayed successfully: 123
```

---

## Authorization & Security

### Driver Route Subscriptions

**File**: `sockets/handlers/subscriptions.py`

When driver subscribes to `route_orders` room:

```python
def _resolve_route_orders_room(claims, params):
    route_id = params.get("route_id")
    team_id = claims.get("team_id")
    user_id = claims.get("user_id")
    
    route_solution = db.session.query(RouteSolution).filter(
        RouteSolution.id == route_id,
        RouteSolution.team_id == team_id,
        RouteSolution.is_selected.is_(True),
        # Driver filtering: only see their assigned routes
        RouteSolution.driver_id == user_id if DRIVER_APP_SCOPE else True
    ).first()
    
    if route_solution is None:
        emit_socket_error("forbidden_route_orders")
        return None
    
    return f"route_orders:{team_id}:{route_id}"
```

**Security Guarantees**:
- ✅ Drivers only see routes assigned to them
- ✅ Teams cannot spy on other teams
- ✅ Routes must be selected (not draft)
- ✅ All checks logged for audit trail

---

## Testing & Monitoring

### E2E Test Scenario

```python
# 1. Admin updates route (assigns driver)
response = client.put(
    f"/api/v2/routes/{route_id}",
    json={"driver_id": driver_user_id},
    headers={"Authorization": f"Bearer {admin_token}"}
)
assert response.status_code == 200

# 2. Wait for event pipeline (1-3 seconds max)
import time
time.sleep(2)

# 3. Check event was created
events = db.session.query(RouteSolutionEvent).filter(
    RouteSolutionEvent.route_solution_id == route_id,
    RouteSolutionEvent.event_name == "route_solution.updated"
).all()
assert len(events) > 0
assert events[0].dispatch_status == "DISPATCHED"  # Dispatcher picked it up
assert events[0].relayed_at is not None  # Worker relayed it

# 4. Check Socket.IO clients received event
# (Monitor browser console or use Socket.IO test client)
```

### Monitoring Checklist

**Daily**:
- [ ] Check dispatcher logs for CRITICAL/ERROR
- [ ] Monitor event table row counts (shouldn't grow unbounded)
- [ ] Check RQ queue depths (shouldn't accumulate)

**Weekly**:
- [ ] Run `event_cleanup_manager.py stats` to see retention
- [ ] Verify `relayed_at` column is being filled (idempotency working)
- [ ] Review stale claims repair count (should be low)

**Monthly**:
- [ ] Archive old events (cleanup script)
- [ ] Analyze event throughput and patterns
- [ ] Plan table growth projections

---

## Common Patterns

### How to Emit an Event on Command Success

**Pattern**: Always create event AFTER commit (to preserve atomicity):

```python
def update_route_solution_fields(ctx, route_solution_id, **changes):
    route_solution = db.session.get(RouteSolution, route_solution_id)
    
    # 1. Update business entity
    old_driver_id = route_solution.driver_id
    for key, value in changes.items():
        if value is not None and getattr(route_solution, key) != value:
            setattr(route_solution, key, value)
    
    # 2. Commit changes
    db.session.commit()
    
    # 3. Create event (separate transaction)
    if route_solution.driver_id != old_driver_id:
        create_route_solution_event(
            ctx=ctx,
            team_id=route_solution.team_id,
            route_solution_id=route_solution.id,
            event_name="route_solution.updated",
            payload={"driver_id": route_solution.driver_id}
        )
```

**Why**:
- If command fails → no event created
- If event creation fails → command already succeeded (acceptable)

### How to Handle Event Bus Suppression

For tests, batch operations, or migrations where you don't want events:

```python
# In test setup
ctx = ctx_with_prevent_event_bus(prevent=True)

# Event creation returns None, no event broadcasted
event = create_route_solution_event(...)
assert event is None  # Event suppressed

# In production
ctx = ctx_normal()  # prevent_event_bus = False by default
event = create_route_solution_event(...)  # Events broadcast normally
```

### How to Query Event History

```python
# Get all events for a route solution
events = db.session.query(RouteSolutionEvent).filter(
    RouteSolutionEvent.route_solution_id == route_id
).order_by(RouteSolutionEvent.occurred_at.asc()).all()

# Get events that failed to relay
failed_events = db.session.query(RouteSolutionEvent).filter(
    RouteSolutionEvent.dispatch_status == "FAIL"
).all()

# Get events pending dispatch
pending_events = db.session.query(RouteSolutionEvent).filter(
    RouteSolutionEvent.dispatch_status == "PENDING"
).all()

# Get events for audit trail (user actions)
user_actions = db.session.query(RouteSolutionEvent).filter(
    RouteSolutionEvent.actor_id == user_id
).order_by(RouteSolutionEvent.occurred_at.desc()).all()
```

---

## Troubleshooting

### Events Not Broadcasting

**Symptoms**: Admin app updates route, driver app doesn't see event

**Checklist**:
```
1. ✅ Event created?
   SELECT * FROM route_solution_event WHERE route_solution_id = ? 
   ORDER BY occurred_at DESC LIMIT 1;
   
2. ✅ Dispatcher claimed it?
   Should have: dispatch_status = 'DISPATCHED' OR 'FAILED'
   
3. ✅ Worker relayed it?
   Should have: relayed_at IS NOT NULL
   
4. ✅ Socket.IO emit succeeded?
   Check logs: "Emitted route_solution.updated: solution_id=..."
   
5. ✅ Driver subscribed to correct room?
   Driver must be in: route_orders:{team_id}:{route_id}
   AND route.driver_id == driver_user_id
   
6. ✅ Event passed validation?
   Check logs for ValidationError in BusinessEventEnvelope
```

### Events Stuck in PENDING

**Symptoms**: Event table growing, dispatch_status always PENDING

**Cause**: Dispatcher not running or crashed

**Fix**:
```bash
# 1. Check dispatcher logs
tail -f log/dispatcher.log

# 2. Check Redis connectivity
redis-cli PING

# 3. Restart dispatcher
python redis_dispatcher.py
```

### Duplicate Events on Frontend

**Symptoms**: Frontend receives same event_id twice

**Root Cause**: RQ retry happened but `relayed_at` not set

**Fix**: Already handled in Phase 2 - check `relayed_at` before emit:
```python
if event_row.relayed_at is not None:
    return  # Skip - already relayed
```

### Slow Event Delivery

**Symptoms**: Events take 10+ seconds to arrive

**Investigation**:
```bash
# 1. Check RQ queue depth
python -c "from Delivery_app_BK.services.infra.jobs.queues import get_named_queue; \
           q = get_named_queue('events'); print(f'Pending: {q.count}')"

# 2. Check dispatcher cycle time (should be 1-3 sec)
grep "dispatch_pending_events" log/dispatcher.log | tail -5

# 3. Check RQ worker lag
rq info  # Shows queue depth and worker idle time

# 4. Scale workers if needed
# Add more RQ workers to process larger batches
```

---

## Additional Resources

- **Phase 1 Summary**: Event models, emitters, DispatchStateMixin
- **Phase 1.5 Summary**: Dispatcher integration, room architecture
- **Phase 2 Implementation**: Command wire-up, event_helpers, logging/validation
- **DB Migration**: `migrations/versions/add_relayed_at_column.py`
- **Cleanup Manager**: `event_cleanup_manager.py`

---

## Quick Reference

| Question | Answer | File |
|----------|--------|------|
| How do I emit an event? | Use `event_helpers.py` functions | `event_helpers.py` |
| Where do events get stored? | Event tables (OrderEvent, RouteSolutionEvent, etc.) | `models/tables/` |
| How does dispatcher work? | Polls PENDING events, enqueues to RQ, marks DISPATCHED | `dispatcher.py` |
| How does relay work? | RQ worker fetches entity, calls emit function, marks relayed_at | `realtime.py` |
| How do Socket.IO rooms work? | Admin/driver split by team, drivers filtered by route assignment | `subscriptions.py` |
| How do I debug? | Grep logs for event_id, follow through each stage | `cli output` |
| How do I clean old events? | Use `event_cleanup_manager.py cleanup` | `cleanup.py` |
| What if something goes wrong? | Check logs, run troubleshooting checklist above | `TBD` |

