# Notification Descriptions — Audit, Registry Refactor & Enrichment Plan

> **Scope:** `Delivery_app_BK/sockets/notifications.py` and the emitter files it depends on.
> **Goal:** (1) Replace the description if-chain with a registry so adding a new event is one line.
> (2) Fix emitters that omit context needed for rich descriptions. (3) Improve the vague descriptions.
>
> Implement in the three phases below in order. Each phase is independently releasable.

---

## Background

There are three public notification entry-points in `notifications.py`:

| Function | Who calls it | Order object available? |
|---|---|---|
| `notify_order_event` (~line 128) | Order event handlers | ✅ loaded from DB |
| `notify_app_event` (~line 251) | App-level event handlers | ✅ loaded from DB if `order_id` in payload |
| `notify_delivery_planning_event` (~line 318) | Route emitters | ❌ always `order=None` |

All three converge on two private builders:

```
_build_notification_title(event_name: str) -> str          # dict-based registry ✅
_build_notification_description(event_name, order, payload) -> str  # if-chain ❌
```

The title is already a registry. The description must follow the same pattern.

---

## Current description quality audit

| Event | Current text | Problem |
|---|---|---|
| `order.created` | "Order #123 was created." | ✅ |
| `order.updated` | "Order #123 details and items were updated." | ✅ uses `changed_sections` |
| `order.state_changed` | "Order #123 moved from Preparing to Ready." | ✅ |
| `order_case.created` | "A new case was created for Order #123." | ✅ |
| `order_case.updated` | "A case for Order #123 was updated." | ⚠️ no detail |
| `order_case.state_changed` | "A case for Order #123 changed to {state}." | ✅ |
| `order_chat.message_created` | first 140 chars of message | ✅ |
| `route_plan.created` | "Delivery plan was created." | ❌ label missing from payload |
| `route_plan.updated` | "Delivery plan was updated." | ❌ label missing; also `notify_delivery_planning_event` is never called by this emitter |
| `route_plan.deleted` | "Delivery plan was deleted." | ❌ label missing from payload |
| `route_group.updated` | "Delivery plan was updated." | ⚠️ has `label` but not `plan_type`; description uses wrong label key |
| `route_solution.created` | "Route 'variant 1' on Local delivery plan 'Morning Run' was created." | ✅ |
| `route_solution.updated` | "Route 'variant 1' on Local delivery plan 'Morning Run' was updated." | ⚠️ `driver_id`, `expected_start_time`, `expected_end_time` in payload but unused |
| `route_solution.deleted` | "Route was deleted." | ❌ `label`/`plan_label` missing from payload |
| `route_solution_stop.updated` | "Stop 3 on Route 'variant 1' — John S., arriving today 15:30." | ✅ (recently improved) |

---

## Phase 1 — Registry refactor (pure refactor, no behavior change)

**File:** `Delivery_app_BK/sockets/notifications.py`

### What to do

Replace the if-chain inside `_build_notification_description` (lines ~628–686) with a
`_DESCRIPTION_BUILDERS` registry dict whose values are callable builder functions,
then reduce `_build_notification_description` to a single lookup + dispatch.

### Target shape

```python
# ── type alias ──────────────────────────────────────────────────────────────
from typing import Callable
_DescriptionBuilder = Callable[["Order | None", dict], str]

# ── individual builder functions (private, one per event) ────────────────────

def _describe_order_created(order: "Order | None", payload: dict) -> str:
    return f"{_build_order_label(order)} was created."

def _describe_order_updated(order: "Order | None", payload: dict) -> str:
    return _build_order_updated_description(
        order_label=_build_order_label(order), payload=payload
    )

def _describe_order_state_changed(order: "Order | None", payload: dict) -> str:
    order_label = _build_order_label(order)
    old_state = _resolve_old_order_state_name(payload=payload)
    new_state = _resolve_new_order_state_name(payload=payload, order=order)
    if old_state and new_state and old_state != new_state:
        return f"{order_label} moved from {old_state} to {new_state}."
    if new_state:
        return f"{order_label} moved to {new_state}."
    return f"{order_label} changed state."

def _describe_order_case_created(order: "Order | None", payload: dict) -> str:
    return f"A new case was created for {_build_order_label(order)}."

def _describe_order_case_updated(order: "Order | None", payload: dict) -> str:
    return f"A case for {_build_order_label(order)} was updated."

def _describe_order_case_state_changed(order: "Order | None", payload: dict) -> str:
    state = payload.get("state")
    order_label = _build_order_label(order)
    if isinstance(state, str) and state.strip():
        return f"A case for {order_label} changed to {state.strip()}."
    return f"A case for {order_label} changed state."

def _describe_order_chat_message_created(order: "Order | None", payload: dict) -> str:
    message = str(payload.get("message") or "").strip()
    if message:
        return message[:140]
    return f"There is a new message for {_build_order_label(order)}."

def _describe_route_plan_created(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_plan_label(payload)} was created."

def _describe_route_plan_updated(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_plan_label(payload)} was updated."

def _describe_route_plan_deleted(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_plan_label(payload)} was deleted."

def _describe_route_group_updated(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_plan_label(payload)} was updated."

def _describe_route_solution_created(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_route_subject_label(payload)} was created."

def _describe_route_solution_updated(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_route_subject_label(payload)} was updated."

def _describe_route_solution_deleted(order: "Order | None", payload: dict) -> str:
    return f"{_resolve_route_subject_label(payload)} was deleted."

def _describe_route_solution_stop_updated(order: "Order | None", payload: dict) -> str:
    route_label = _resolve_route_label(payload)
    stop_order = _parse_int(payload.get("stop_order"))
    stop_label = f"Stop {stop_order}" if stop_order is not None else "A stop"
    client_label = payload.get("notification_client_label")
    arrival_label = payload.get("notification_arrival_label")
    if client_label and arrival_label:
        return f"{stop_label} on {route_label} — {client_label}, arriving {arrival_label}."
    if client_label:
        return f"{stop_label} on {route_label} — {client_label} was updated."
    if arrival_label:
        return f"{stop_label} on {route_label} — arriving {arrival_label}."
    return f"{stop_label} on {route_label} was updated."

# ── registry ─────────────────────────────────────────────────────────────────

_DESCRIPTION_BUILDERS: dict[str, _DescriptionBuilder] = {
    "order.created":                  _describe_order_created,
    "order.updated":                  _describe_order_updated,
    "order.state_changed":            _describe_order_state_changed,
    "order_case.created":             _describe_order_case_created,
    "order_case.updated":             _describe_order_case_updated,
    "order_case.state_changed":       _describe_order_case_state_changed,
    "order_chat.message_created":     _describe_order_chat_message_created,
    "route_plan.created":             _describe_route_plan_created,
    "route_plan.updated":             _describe_route_plan_updated,
    "route_plan.deleted":             _describe_route_plan_deleted,
    "route_group.updated":            _describe_route_group_updated,
    "route_solution.created":         _describe_route_solution_created,
    "route_solution.updated":         _describe_route_solution_updated,
    "route_solution.deleted":         _describe_route_solution_deleted,
    "route_solution_stop.updated":    _describe_route_solution_stop_updated,
}

# ── dispatch ──────────────────────────────────────────────────────────────────

def _build_notification_description(
    *, event_name: str, order: "Order | None", payload: dict
) -> str:
    builder = _DESCRIPTION_BUILDERS.get(event_name)
    if builder is None:
        return "A new update is available."
    return builder(order, payload)
```

### Rules for Codex

- Delete the entire existing if-chain body of `_build_notification_description` (lines ~634–686).
- Replace it with the registry + dispatch shown above.
- The helper functions `_build_order_label`, `_resolve_plan_label`, `_resolve_route_label`,
  `_resolve_route_subject_label`, `_resolve_old_order_state_name`, `_resolve_new_order_state_name`,
  `_build_order_updated_description`, and `_parse_int` already exist in the file — do not rewrite them.
- Place all `_describe_*` functions directly above the `_DESCRIPTION_BUILDERS` dict.
- Place the dict directly above the redefined `_build_notification_description` function.
- All builder functions must have type hints on all parameters and return type.
- No behavior change in Phase 1. All descriptions must produce identical output to today.

---

## Phase 2 — Fix emitter payloads

These are the emitters where the payload is missing context that the description builders need.
Fix each emitter independently.

### 2A — `route_solution.deleted` — missing `label` and `plan_label`

**File:** `Delivery_app_BK/sockets/emitters/route_solution_events.py`
**Function:** `emit_route_solution_deleted_for_route_group` (~line 138)

**Problem:** The solution object is already deleted before this function is called, so only
`route_solution_id` (int) is available. The `route_group` IS loaded from DB at line 152.
The plan is available via `route_group.route_plan`.

**Fix:** The `payload` kwarg at the call-site must carry `label` and `plan_label` before the
solution is deleted. The call-sites must be updated to pass these.

Find all call-sites of `emit_route_solution_deleted_for_route_group` and
`emit_route_solution_deleted` in the codebase. At each call-site, before the solution is
deleted, capture:

```python
solution_label = route_solution.label
plan_label = route_solution.route_group.route_plan.label if ... else None
plan_type = resolve_route_plan_workflow_type()
```

Then pass them via the `payload` kwarg:

```python
emit_route_solution_deleted_for_route_group(
    team_id=...,
    route_group_id=...,
    route_solution_id=...,
    payload={
        "label": solution_label,
        "plan_label": plan_label,
        "plan_type": plan_type,
    },
)
```

The emitter's `**(payload or {})` spread already handles this — no change needed inside the emitter.

### 2B — `route_group.updated` — missing `plan_type`

**File:** `Delivery_app_BK/sockets/emitters/route_group_events.py`
**Function:** `emit_route_group_updated` (~line 11)

**Problem:** The payload has `label` (the plan label) but is missing `plan_type`, so
`_resolve_plan_label` cannot choose the right prefix ("Local delivery plan" vs "Route plan").

**Fix:** Add `plan_type` to the envelope payload. Import `resolve_route_plan_workflow_type`
from wherever it is used in `route_solution_events.py` (same import already exists there).

```python
# In the payload dict (after "label": route_plan.label):
"plan_type": resolve_route_plan_workflow_type(),
```

Also note: the `_describe_route_group_updated` builder calls `_resolve_plan_label(payload)`,
which looks for `payload["label"]` as the plan label. The `route_group_events.py` emitter
already puts the plan label under `"label"` key — this is correct for `_resolve_plan_label`.

### 2C — `route_plan.*` events — investigate and fix

**File:** `Delivery_app_BK/sockets/emitters/route_plan_events.py`
**Function:** `emit_delivery_plan_totals_updated` (~line 13)

**Problem (two separate issues):**

1. This emitter fires `route_plan.updated` but does **not** call `notify_delivery_planning_event`,
   so no persistent notification is generated. This is likely intentional (totals are background
   noise) — **do not add** `notify_delivery_planning_event` here.

2. `route_plan.created` and `route_plan.deleted` events: search the codebase for wherever
   these events are emitted (grep for `BUSINESS_EVENT_ROUTE_PLAN_CREATED` and
   `BUSINESS_EVENT_ROUTE_PLAN_DELETED` or `"route_plan.created"` / `"route_plan.deleted"`).
   At each call-site, verify the payload includes `"label"`, `"plan_type"`, and that
   `notify_delivery_planning_event` is called. If `label` is missing, add it from the
   `RoutePlan` object (`plan.label`, `plan.plan_type` or `resolve_route_plan_workflow_type()`).

---

## Phase 3 — Improve vague description builders

After Phase 1 (registry in place) and Phase 2 (payloads enriched), update individual builder
functions to produce richer output. Each change is isolated to one `_describe_*` function.

### 3A — `route_solution.deleted` → show route + plan name

**After Phase 2A** the payload will have `label` and `plan_label`. Update
`_describe_route_solution_deleted`:

```python
def _describe_route_solution_deleted(order: "Order | None", payload: dict) -> str:
    route_label = _resolve_route_label(payload)
    plan_label = payload.get("plan_label")
    if plan_label and isinstance(plan_label, str) and plan_label.strip():
        plan_type = payload.get("plan_type") or ""
        prefix = (
            "Local delivery plan" if plan_type == "local_delivery"
            else "Route plan" if plan_type == "route_plan"
            else "Plan"
        )
        return f"{route_label} on {prefix} \"{plan_label.strip()}\" was deleted."
    return f"{route_label} was deleted."
```

Example output: `Route "variant 1" on Local delivery plan "Morning Run" was deleted.`

### 3B — `route_group.updated` → show plan name + meaningful context

**After Phase 2B** the payload has `label` (plan label) and `plan_type`. Update
`_describe_route_group_updated`:

```python
def _describe_route_group_updated(order: "Order | None", payload: dict) -> str:
    plan_label = _resolve_plan_label(payload)
    stop_count = payload.get("total_stops")
    order_count = payload.get("total_orders")
    if isinstance(stop_count, int) and isinstance(order_count, int):
        return f"{plan_label} was updated — {order_count} orders across {stop_count} stops."
    return f"{plan_label} was updated."
```

Note: `total_stops` and `total_orders` are not currently in the payload. If you want this
richer form, add them in the emitter. If not, the simpler form (`"{plan_label} was updated."`)
is already an improvement over the current fallback text.

### 3C — `route_solution.updated` → surface meaningful change hints

The emitter payload already includes `driver_id`, `expected_start_time`, `expected_end_time`,
`is_selected`. Callers can also pass extra context via the `payload` kwarg. Add a
`notification_change_hint` field convention: callers set it at the emit call-site to a short
string describing what changed (e.g. `"driver_assigned"`, `"route_optimized"`, `"times_updated"`).

```python
def _describe_route_solution_updated(order: "Order | None", payload: dict) -> str:
    route_subject = _resolve_route_subject_label(payload)
    hint = payload.get("notification_change_hint")
    if hint == "driver_assigned":
        return f"{route_subject} — driver was assigned."
    if hint == "route_optimized":
        return f"{route_subject} was optimized."
    if hint == "times_updated":
        return f"{route_subject} — arrival times were updated."
    return f"{route_subject} was updated."
```

Update each call-site of `emit_route_solution_updated` to pass the appropriate hint:

```python
emit_route_solution_updated(
    route_solution,
    payload={"notification_change_hint": "driver_assigned"},
)
```

### 3D — `order_case.updated` → surface changed sections (optional)

The `order.updated` handler already uses `changed_sections` from the payload. If the case
update emitter also sets `changed_sections` (e.g. `["notes"]`, `["status"]`), the builder
can use it. This is a call-site concern; the builder pattern is the same as `_describe_order_updated`.

---

## File change summary

| File | Phase | Change |
|---|---|---|
| `sockets/notifications.py` | 1 | Replace if-chain with `_DESCRIPTION_BUILDERS` registry |
| `sockets/emitters/route_solution_events.py` | 2A | Call-sites of `emit_route_solution_deleted*` must pass `label`, `plan_label`, `plan_type` in `payload` kwarg before deletion |
| `sockets/emitters/route_group_events.py` | 2B | Add `plan_type` to envelope payload |
| Wherever `route_plan.created/deleted` are emitted | 2C | Verify `label`, `plan_type` in payload |
| `sockets/notifications.py` `_describe_route_solution_deleted` | 3A | Use `plan_label` from payload |
| `sockets/notifications.py` `_describe_route_group_updated` | 3B | Use `label` + `plan_type` |
| `sockets/notifications.py` `_describe_route_solution_updated` | 3C | Use `notification_change_hint` from payload |
| Call-sites of `emit_route_solution_updated` | 3C | Pass `notification_change_hint` in `payload` kwarg |

---

## Convention established by this plan

**`notification_*` payload fields** are UI hints added by emitters for the notification layer.
They are pre-computed at emission time (when the DB session and full object graph are available)
and read by `_describe_*` builder functions. Current fields:

| Field | Set by | Used by |
|---|---|---|
| `notification_client_label` | `route_solution_stop_events.py` | `_describe_route_solution_stop_updated` |
| `notification_arrival_label` | `route_solution_stop_events.py` | `_describe_route_solution_stop_updated` |
| `notification_change_hint` | call-sites of `emit_route_solution_updated` | `_describe_route_solution_updated` |

Follow this same `notification_*` prefix convention for any new hint fields in future emitters.

---

## Adding a new notification event (after this plan is implemented)

1. Add the event name → title string to `_TITLE_REGISTRY` (or the existing dict in `_build_notification_title`).
2. Write a `_describe_<event_name>(order, payload) -> str` function.
3. Add one entry to `_DESCRIPTION_BUILDERS`.
4. In the emitter, add any `notification_*` context fields needed by the builder.

That is the complete contract. No other files need to change.
