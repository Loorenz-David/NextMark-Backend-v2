# Actor-Aware Notifications — Route Domain

> **Problem:** Every notification in the route domain (`route_solution.*`, `route_solution_stop.*`,
> `route_group.*`) is sent to ALL eligible recipients, including the user who made the change.
> They get notified about their own action, which is noisy and confusing.
>
> **Root cause:** Every route emitter passes `actor=None` to `notify_delivery_planning_event`.
> The suppression logic already exists — it just never fires because it has no actor to compare.
>
> **Goal:** Wire the authenticated user (actor) through the route emitter layer so notifications
> exclude the actor, and the notification record carries `actor_user_id` and `actor_username`.

---

## How the working path looks (order events)

Order events already handle this correctly. The chain is:

```
OrderEvent.actor_id  →  OrderEvent.actor (User, loaded via selectin relationship)
                             ↓
                     notify_order_event(actor=event_row.actor)
                             ↓
              resolve_admin_notification_recipients(actor_user_id=actor.id)
              → filters out actor.id from recipient list ✅

              build_notification_item(actor=actor)
              → actor_user_id=actor.id, actor_username=actor.username ✅
```

The route path currently:

```
HTTP request → command (has ctx.user_id) → emitter(actor=None)
                                                    ↓
                                    notify_delivery_planning_event(actor=None)
                                                    ↓
                         resolve_admin_notification_recipients(actor_user_id=None)
                         → actor is never filtered out ❌

                         build_notification_item(actor=None)
                         → actor_user_id=None, actor_username=None ❌
```

---

## Key facts about the existing system

- `build_notification_item` ([notifications.py ~line 533]) accepts `actor: User | None`.
  It reads `actor.id` → `actor_user_id` and `actor.username` → `actor_username` on the
  notification record. The `User.username` column exists (`models/tables/users/user.py:32`).

- `_resolve_actor_username(actor)` is already implemented in `notifications.py`. It simply
  reads `actor.username`. No changes needed there.

- `resolve_admin_notification_recipients` and `resolve_driver_notification_recipients` already
  filter `user_id != actor_user_id`. No changes needed there either.

- `ServiceContext.user_id` (`services/context.py:56`) returns the authenticated user's integer
  ID from the JWT identity dict. It is always populated for authenticated routes.

- All route command files receive `ctx: ServiceContext`. The User object for the actor can be
  fetched with `db.session.get(User, ctx.user_id)`. Because the auth middleware already loaded
  this user during JWT validation, SQLAlchemy's identity map returns it from the session cache —
  no extra DB round-trip.

---

## Affected emitter files and functions

| File | Functions to update |
|---|---|
| `sockets/emitters/route_solution_stop_events.py` | `emit_route_solution_stop_updated`, `notify_route_solution_stops_batch_updated` |
| `sockets/emitters/route_solution_events.py` | `emit_route_solution_created`, `emit_route_solution_updated`, `emit_route_solution_deleted_for_route_group` |
| `sockets/emitters/route_group_events.py` | `emit_route_group_updated` |

`route_plan_events.py` (`emit_delivery_plan_totals_updated`) does **not** call
`notify_delivery_planning_event`, so it requires no change.

---

## Phase 1 — Add `actor` parameter to all route emitter functions

For every function listed in the table above, add a keyword-only parameter:

```python
actor: "User | None" = None,
```

This parameter must be forwarded to every `notify_delivery_planning_event(...)` call inside
that function.

### Example — `emit_route_solution_stop_updated`

**Before:**
```python
def emit_route_solution_stop_updated(
    route_solution_stop: RouteSolutionStop,
    *,
    payload: dict | None = None,
    notify: bool = True,
) -> None:
    ...
    if notify:
        notify_delivery_planning_event(
            ...
            actor=None,
        )
```

**After:**
```python
def emit_route_solution_stop_updated(
    route_solution_stop: RouteSolutionStop,
    *,
    payload: dict | None = None,
    notify: bool = True,
    actor: "User | None" = None,
) -> None:
    ...
    if notify:
        notify_delivery_planning_event(
            ...
            actor=actor,
        )
```

### Example — `notify_route_solution_stops_batch_updated`

**Before:**
```python
def notify_route_solution_stops_batch_updated(
    route_solution: RouteSolution,
    affected_stop_count: int,
    change_hint: str,
) -> None:
    ...
    notify_delivery_planning_event(
        ...
        actor=None,
    )
```

**After:**
```python
def notify_route_solution_stops_batch_updated(
    route_solution: RouteSolution,
    affected_stop_count: int,
    change_hint: str,
    *,
    actor: "User | None" = None,
) -> None:
    ...
    notify_delivery_planning_event(
        ...
        actor=actor,
    )
```

Apply the identical pattern to every function in the affected emitter files. The default
`actor=None` means all existing call-sites that do not pass an actor continue to work
without modification — the suppression just doesn't fire for them.

---

## Phase 2 — Supply the actor at every call-site

Every command file that calls a route emitter must:

1. Load the `User` object for the authenticated actor.
2. Pass it to the emitter call.

### Loading the actor (do this once per command function, before the emit loop)

```python
from Delivery_app_BK.models import User, db

actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
```

This is a session-cache hit — the auth middleware already fetched this user. It is a single
`db.session.get` call, not a new query.

### Call-site changes

#### `stops/update_route_stop_position.py`

Load actor before the emit section, pass to both calls:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

for stop in all_affected_stops:
    create_route_solution_stop_event(...)
    emit_route_solution_stop_updated(stop, notify=False, actor=actor)

notify_route_solution_stops_batch_updated(
    route_solution=route_solution,
    affected_stop_count=len(all_affected_stops),
    change_hint="stops_reordered",
    actor=actor,
)
```

#### `stops/update_route_stop_group_position.py`

Same pattern:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

for stop in changed_stops:
    create_route_solution_stop_event(...)
    emit_route_solution_stop_updated(stop, notify=False, actor=actor)

notify_route_solution_stops_batch_updated(
    route_solution=route_solution,
    affected_stop_count=len(changed_stops),
    change_hint="stops_reordered",
    actor=actor,
)
```

#### `stops/update_route_stop_service_time.py`

Same pattern:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

for stop in changed_stops:
    create_route_solution_stop_event(...)
    emit_route_solution_stop_updated(stop, notify=False, actor=actor)

notify_route_solution_stops_batch_updated(
    route_solution=route_solution,
    affected_stop_count=len(changed_stops),
    change_hint="service_time_updated",
    actor=actor,
)
```

#### `stops/mark_route_stop_actual_arrival_time.py`

Single-stop, `notify=True` default. Load actor and pass:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
emit_route_solution_stop_updated(route_stop, payload={...}, actor=actor)
```

#### `stops/mark_route_stop_actual_departure_time.py`

Same as arrival:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
emit_route_solution_stop_updated(route_stop, payload={...}, actor=actor)
```

#### `local_delivery/update_settings.py`

Two emitter calls in this file. Load actor once, pass to both:

```python
actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

# existing emit_route_solution_updated calls — add actor=actor to each
emit_route_solution_updated(route_solution, payload={...}, actor=actor)

# per-stop loop
for stop in affected_stops:
    create_route_solution_stop_event(...)
    emit_route_solution_stop_updated(stop, notify=False, actor=actor)

if not route_solution_changed:
    notify_route_solution_stops_batch_updated(
        route_solution=route_solution,
        affected_stop_count=len(affected_stops),
        change_hint="settings_updated",
        actor=actor,
    )
```

#### All other call-sites of `emit_route_solution_created`, `emit_route_solution_updated`, `emit_route_solution_deleted_for_route_group`, `emit_route_group_updated`

Find every call-site by searching for the function name. For each one:
- Check if the call-site has a `ctx` in scope.
- If yes: load actor with `db.session.get(User, ctx.user_id) if ctx.user_id else None` and pass `actor=actor`.
- If no (e.g. background jobs, system-triggered events): pass nothing — the `actor=None` default remains correct. System-initiated changes should still notify all recipients.

---

## What the notification record looks like after this change

For a user "alice" (user_id=42) who reorders stops on a route:

```json
{
  "actor_user_id": 42,
  "actor_username": "alice",
  "title": "Route updated",
  "description": "Route 'Morning Run' — stops were reordered.",
  "kind": "route_solution.updated"
}
```

Alice does **not** receive this notification. Every other admin on the team does.
The driver on the route does, unless the driver is also the actor (rare but handled).

---

## What does NOT need to change

- `notifications.py` — `resolve_admin_notification_recipients`, `resolve_driver_notification_recipients`,
  `build_notification_item`, `_resolve_actor_username` — all already correct.
- `services/context.py` — `ctx.user_id` already exists.
- `models/tables/users/user.py` — `User.username` already exists.
- Order event notification path — already works correctly, untouched.

---

## Verification checklist

After implementing:

- [ ] Log in as user A (admin). Make a route stop change. Confirm user A does NOT receive a notification.
- [ ] Log in as user B (admin, same team). Confirm user B DOES receive the notification with `actor_username = "A"`.
- [ ] Check the notification record in the database/Redis: `actor_user_id` and `actor_username` are populated.
- [ ] Driver notification: confirm the driver receives the notification when a stop on their assigned route is changed by an admin.
- [ ] System-triggered changes (background jobs, AI operator): confirm notifications still fire to all recipients (actor=None path unchanged).
- [ ] Single-stop changes (actual arrival/departure time marking): confirm actor suppression applies to these too.
