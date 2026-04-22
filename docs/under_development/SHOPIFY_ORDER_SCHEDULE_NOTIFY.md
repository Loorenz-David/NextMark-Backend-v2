# Order Schedule Notification — Outbound (Multi-Target)

> **Problem:** When an order is assigned to a plan on creation, or when its delivery date
> changes through a reschedule, external services must be notified of the new scheduled date.
> A single env-var endpoint cannot support multiple subscribers, and adding a new external
> service would require a code deploy instead of a DB record.
>
> **Goal:** Introduce a `OrderScheduleTarget` model that registers any number of external
> HTTP endpoints per team. On `ORDER_CREATED` (if the order is on a plan with a date) and
> on `DELIVERY_RESCHEDULED` (if a new plan date is present), the event handler fans out
> one background job per active target registered for that team. Each job POSTs the
> scheduled date to its target's endpoint using that target's own credentials.
> Adding a new external service = inserting a DB row. No code change required.

---

## External API Contract (per target)

```
POST {target.endpoint_url}
x-api-key: {target.api_key}
Content-Type: application/json

{
  "shopId":        "{target.external_shop_id}",
  "orderId":       "{order.external_order_id}",
  "scheduledDate": "YYYY-MM-DD"
}
```

Each `OrderScheduleTarget` carries its own `endpoint_url`, `api_key`, and `external_shop_id`.
Different targets can point to different systems with different credentials — no shared config.

`scheduledDate` is always `YYYY-MM-DD`, extracted from the plan's `start_date` (UTC date portion).
This applies to both `date_strategy = "single"` and `date_strategy = "range"` plans — always
`start_date`, never `end_date`. For range plans `end_date` is intentionally ignored.
`orderId` is `order.external_order_id` — the Shopify numeric order ID stored on the Order row.

---

## Trigger Conditions

### Trigger 1 — Order creation on a plan

Event: `ORDER_CREATED` (fired by `create_order.py` via `emit_order_events`).

Fan out to all active targets **only when all of these are true**:
- `order.external_order_id` is set (order came from an external source)
- The event payload carries a `delivery_plan_id`
- The loaded `RoutePlan.start_date` is not `None`

### Trigger 2 — Delivery rescheduled

Event: `DELIVERY_RESCHEDULED` (fired from `update_order_route_plan.py`,
`route_plan/update_plan.py`, and `route_plan/local_delivery/update_settings.py`).

Fan out to all active targets **only when all of these are true**:
- `order.external_order_id` is set
- `payload["new_plan_start"]` is a non-null string (the new plan date exists)

---

## Existing Architecture Anchors

### Integration model pattern
All integration models follow the same shape:
- Live in `models/tables/integrations/`
- Mix in `TeamScopedMixin` for `team_id`
- Have a `team` relationship
- Are registered in `models/__init__.py`

`TwilioMod`, `EmailSMTP`, `ShopifyIntegration` are the direct precedents.

### Event bus → handler → enqueue → task → command
Established pattern from `fulfill_shopify_order`:
```
OrderEvent.COMPLETED
    → handlers/order/order_shopify.py
        → enqueue_job(fn=tasks/order/fulfill_shopify_order)
            → commands/integration_shopify/ingestions/outbound/order/fulfill_shopify_order.py
                → requests.post(Shopify API)
```
The new feature follows this layering. The handler fans out one `enqueue_job` call per active
target, each job carrying `(target_id, order_id, scheduled_date)`.

### Domain guard
`services/domain/order/shopify.py` already has `is_shopify_order(order)`.
A new, broader guard `should_notify_order_schedule(order)` checks only that
`external_order_id` is present — it does not restrict by `external_source`. Any externally
sourced order with an `external_order_id` qualifies. The old
`should_notify_shopify_schedule` name is dropped.

---

## What Changes — Six Layers

### 1. New model

**Create** `models/tables/integrations/order_schedule_target.py`

Single responsibility: one row = one external service that receives schedule notifications.

```python
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class OrderScheduleTarget(db.Model, TeamScopedMixin):
    __tablename__ = "order_schedule_targets"

    id              = Column(Integer, primary_key=True)
    client_id       = Column(String, index=True)
    name            = Column(String, nullable=False)         # human label: "POS System"
    endpoint_url    = Column(String, nullable=False)
    api_key         = Column(String, nullable=False)
    external_shop_id = Column(String, nullable=True)         # "shopId" in the POST body
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(UTCDateTime, nullable=False,
                             default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(UTCDateTime, nullable=False,
                             default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    team = relationship("Team", backref="order_schedule_targets", lazy=True)
```

**Register in** `models/__init__.py`:
```python
from .tables.integrations.order_schedule_target import OrderScheduleTarget
```

**Generate Alembic migration** after the model is registered:
```bash
flask db migrate -m "add order_schedule_targets table"
```

Fields:
- `name` — human label so operators know what each row represents
- `external_shop_id` — the `"shopId"` sent in the POST body; each target can have a
  different identifier for the same shop
- `is_active` — disable a target without deleting it; handlers only query active rows
- `api_key` is stored as plain text for now (same approach as `ShopifyIntegration.access_token`)

---

### 2. Domain guard (extend existing file)

**Edit** `services/domain/order/shopify.py` — add one new guard:

```python
def should_notify_order_schedule(order: Any) -> bool:
    return bool(getattr(order, "external_order_id", None))
```

No `external_source` restriction — any order with an `external_order_id` qualifies.
The Shopify-specific check (`is_shopify_order`) is kept for the existing fulfillment guard.
This new guard is intentionally broader.

---

### 3. Outbound command (new file)

**Create** `services/commands/integration_shopify/ingestions/outbound/order/notify_order_schedule.py`

Single responsibility: load one target, make one POST.

```python
import logging
import requests

from Delivery_app_BK.models import Order, OrderScheduleTarget, db
from Delivery_app_BK.services.domain.order.shopify import should_notify_order_schedule

logger = logging.getLogger(__name__)


def notify_order_schedule(
    target_id: int,
    order_id: int,
    scheduled_date: str,
) -> None:
    target = db.session.get(OrderScheduleTarget, target_id)
    if target is None or not target.is_active:
        return

    order = db.session.get(Order, order_id)
    if order is None or not should_notify_order_schedule(order):
        return

    response = requests.post(
        target.endpoint_url,
        headers={
            "x-api-key": target.api_key,
            "Content-Type": "application/json",
        },
        json={
            "shopId":        target.external_shop_id,
            "orderId":       order.external_order_id,
            "scheduledDate": scheduled_date,
        },
        timeout=10,
    )
    response.raise_for_status()

    logger.info(
        "Order schedule notified | target=%s order_id=%s external_order_id=%s date=%s",
        target_id,
        order_id,
        order.external_order_id,
        scheduled_date,
    )
```

Rules:
- `raise_for_status()` is intentional — HTTP errors propagate so RQ retries the job.
- Re-checks `is_active` and the domain guard inside the command as a last-resort defence,
  consistent with how `fulfill_shopify_order` re-checks `should_fulfill_shopify_order`.
- No env vars anywhere in this file.

---

### 4. RQ task (new file)

**Create** `services/infra/tasks/order/notify_order_schedule.py`

```python
from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order.notify_order_schedule import (
    notify_order_schedule as _command,
)


def notify_order_schedule(target_id: int, order_id: int, scheduled_date: str) -> None:
    _command(target_id, order_id, scheduled_date)
```

Thin wrapper. Identical in shape to `tasks/order/fulfill_shopify_order.py`.

---

### 5. Event handlers (extend existing file)

**Edit** `services/infra/events/handlers/order/order_shopify.py` — add two handlers.

Add to imports:
```python
from Delivery_app_BK.models import Order, OrderScheduleTarget, RoutePlan
from Delivery_app_BK.services.domain.order.shopify import should_notify_order_schedule
from Delivery_app_BK.services.infra.tasks.order.notify_order_schedule import notify_order_schedule
```

**Handler A — Order creation on a plan:**

```python
def notify_schedule_targets_on_order_created(order_event) -> None:
    payload = getattr(order_event, "payload", None) or {}
    delivery_plan_id = payload.get("delivery_plan_id")
    if not delivery_plan_id:
        return

    order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not should_notify_order_schedule(order):
        return

    plan = db.session.get(RoutePlan, delivery_plan_id)
    start_date = getattr(plan, "start_date", None) if plan else None
    if start_date is None:
        return

    scheduled_date = start_date.date().isoformat()
    _fan_out_schedule_notification(order, scheduled_date)
```

**Handler B — Delivery rescheduled:**

```python
def notify_schedule_targets_on_delivery_rescheduled(order_event) -> None:
    payload = getattr(order_event, "payload", None) or {}
    new_plan_start = payload.get("new_plan_start")
    if not new_plan_start:
        return

    order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None or not should_notify_order_schedule(order):
        return

    scheduled_date = new_plan_start[:10]   # YYYY-MM-DD from ISO datetime
    _fan_out_schedule_notification(order, scheduled_date)
```

**Shared fan-out helper (private to this module):**

```python
def _fan_out_schedule_notification(order: Order, scheduled_date: str) -> None:
    targets = (
        db.session.query(OrderScheduleTarget)
        .filter(
            OrderScheduleTarget.team_id == order.team_id,
            OrderScheduleTarget.is_active.is_(True),
        )
        .all()
    )
    for target in targets:
        enqueue_job(
            queue_key="default",
            fn=notify_order_schedule,
            args=(target.id, order.id, scheduled_date),
            description=f"notify-order-schedule:{target.id}:{order.id}",
        )
```

The helper is private (underscore prefix) because it is only meaningful within this handler
module — it is not a domain function and must not be called from outside `order_shopify.py`.

---

### 6. Event registry (extend existing file)

**Edit** `services/infra/events/registry/order.py`:

Add to the existing import of `order_shopify` handlers:
```python
from Delivery_app_BK.services.infra.events.handlers.order.order_shopify import (
    # existing:
    sync_shopify_fulfillment_on_order_completed,
    # new:
    notify_schedule_targets_on_order_created,
    notify_schedule_targets_on_delivery_rescheduled,
)
```

Add two registrations inside `register_order_event_handlers`:
```python
event_bus.register(
    OrderEvent.CREATED.value,
    notify_schedule_targets_on_order_created,
)
event_bus.register(
    OrderEvent.DELIVERY_RESCHEDULED.value,
    notify_schedule_targets_on_delivery_rescheduled,
)
```

---

## Why This Architecture

### One job per target, not one job for all targets

Each target gets its own RQ job. If target A's endpoint is down, it retries independently
without blocking target B. Job isolation is correct here.

### Fan-out at handler time, not at task time

The handler resolves `scheduled_date` from the event payload and the target list from the
DB at event time — before queuing. Job args are primitives `(int, int, str)`, safe to
serialize for RQ. The task and command have no dependency on loading the plan.

### Handler eager-guards, command re-guards

The handler guards before queuing (avoids polluting the queue). The command re-checks
`is_active` and the domain guard because the RQ job runs asynchronously — a target could
have been deactivated between enqueue and execution.

### No env vars in the critical path

All configuration lives in `order_schedule_targets` rows. Deploying a new external
subscriber = `INSERT INTO order_schedule_targets ...`. No restart, no deploy.

---

## Blast Radius

| Scope | Impact |
|---|---|
| `models/tables/integrations/order_schedule_target.py` | New file; new table via migration |
| `models/__init__.py` | One new import line |
| `domain/order/shopify.py` | One additive guard function |
| `outbound/order/notify_order_schedule.py` | New file; no existing code changed |
| `tasks/order/notify_order_schedule.py` | New file; no existing code changed |
| `handlers/order/order_shopify.py` | Two new handlers + one private helper; existing handlers untouched |
| `registry/order.py` | Two new `event_bus.register` calls; existing registrations untouched |
| Orders with no active targets | Fan-out loop iterates over empty list → no jobs enqueued |
| Non-external orders | `should_notify_order_schedule` returns `False` → early return before query |

---

## Verification Checklist

- [ ] `ORDER_CREATED` for an external order on a plan with 2 active targets → 2 jobs enqueued
- [ ] `ORDER_CREATED` for an external order not on a plan → 0 jobs enqueued
- [ ] `ORDER_CREATED` with plan having no `start_date` → 0 jobs enqueued
- [ ] `ORDER_CREATED` for an order with no `external_order_id` → 0 jobs enqueued
- [ ] `DELIVERY_RESCHEDULED` for an external order with `new_plan_start` and 1 active target → 1 job enqueued
- [ ] `DELIVERY_RESCHEDULED` with `new_plan_start=None` → 0 jobs enqueued
- [ ] Team with 0 active targets → fan-out produces 0 jobs (no error)
- [ ] Target with `is_active=False` → skipped by the query; no job enqueued
- [ ] Target deactivated after enqueue but before job runs → command returns early
- [ ] HTTP 4xx/5xx from external endpoint → `raise_for_status()` raises → RQ retries that job only
- [ ] Job for target A fails; job for target B succeeds → each is independent
- [ ] `scheduledDate` is always `YYYY-MM-DD`
- [ ] Alembic migration runs cleanly on fresh DB and upgrade path
