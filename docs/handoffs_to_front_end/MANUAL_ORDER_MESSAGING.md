# Manual Order Messaging — Frontend Handoff

**Status:** implemented, backend merged
**Audience:** admin-app frontend
**Scope:** letting an operator pick one or more orders, pick a message template (business event), and send or resend that message on email / SMS on demand.

---

## 1. What this feature is

The platform already sends emails and SMS automatically: a command emits a business event (`order_ready`, `order_rescheduled`, …), the event bus fans it out to handlers, and each handler creates an *action* that a worker picks up and sends.

This feature adds a **manual trigger** for the same machinery. The operator chooses the target orders and the template; the backend builds the same kind of action and queues it immediately, skipping the template's schedule offset.

Three calls are involved:

| Step | Call | Purpose |
|---|---|---|
| 1 | `GET /api_v2/message_templates/` | Populate the template picker |
| 2 | `POST /api_v2/order_messages/send` | Trigger the send |
| 3 | `realtime:event` socket frames ([§9](#9-realtime-socket-frames)) | Live delivery status |
| — | `GET /api_v2/orders/{order_id}/events/` | Initial render, reconnect, socket-down fallback |

> **There is no message-body preview endpoint.** See [§8](#8-what-does-not-exist-yet) before designing that part of the UI.

---

## 2. Conventions that apply to every call here

### 2.1 Auth

All three endpoints require:

- `Authorization: Bearer <access_token>`
- JWT claim `app_scope == "admin"` — enforced by a blueprint-level guard
- JWT claim `base_role_id` in `{1, 2}` (`ADMIN`, `ASSISTANT`). `DRIVER` (`3`) is rejected.

Team scoping is implicit: every query is filtered by the `active_team_id` (falling back to `team_id`) claim in the token. You never pass a team id in the body.

### 2.2 Success envelope

```jsonc
{
  "data":     { /* endpoint-specific payload */ },
  "warnings": []            // string[], usually empty
}
```

HTTP `200`.

### 2.3 Error envelope

```jsonc
{
  "error": "Human readable message",
  "code":  "bad_request"
}
```

### 2.4 ⚠️ Non-standard HTTP status codes

The API deliberately offsets error statuses by **+10**, because CloudFront intercepts 400–405 and serves the SPA shell instead of the JSON body. Do not write `if (res.status === 400)`.

| Error class | `code` | HTTP status |
|---|---|---|
| `ValidationFailed` | `bad_request` | **410** |
| `PermissionDenied` | `forbidden` | **413** |
| `NotFound` | `not_found` | **414** |
| `DomainError` (unexpected/internal) | `internal_error` | **510** |

Branch on the `code` field, not the status. Note `410` here means "validation failed", **not** HTTP Gone.

---

## 3. Enums

Copy these verbatim. They are the exact stored string values.

### 3.1 `OrderEventName` — selectable template events

Source: `services/domain/order/order_events.py`.

```ts
type OrderEventName =
  | "order_created"
  | "order_confirmed"
  | "order_preparing"
  | "order_edited"
  | "order_ready"
  | "order_processing"
  | "order_completed"
  | "order_failed"
  | "order_cancelled"
  | "order_status_changed"
  | "order_delivery_window_changed_by_user"
  | "order_delivery_plan_changed"
  | "order_rescheduled"
  | "client_form_link_sent"
  | "client_form_submitted";
```

⚠️ Two names do not follow the pattern you might guess:
- `OrderEvent.FAIL` → `"order_failed"`
- `OrderEvent.DELIVERY_RESCHEDULED` → `"order_rescheduled"` (not `order_delivery_rescheduled`)

### 3.2 `MessageChannel`

```ts
// Stored on MessageTemplate.channel
type MessageChannel = "sms" | "email" | "whatsapp" | "telegram";

// Actually sendable — the only values accepted by the send endpoint
type SendableChannel = "email" | "sms";
```

`whatsapp` and `telegram` templates can exist in the database but have **no sender implementation**. Filter them out of the manual-send UI or the request will be rejected.

### 3.3 `ActionStatus` — per-message delivery state

```ts
type ActionStatus = "PENDING" | "SUCCESS" | "FAILED" | "SKIPPED";
```

| Value | Meaning |
|---|---|
| `PENDING` | Queued, not yet attempted. |
| `SUCCESS` | Handed to the SMTP / Twilio provider without error. Terminal. |
| `FAILED` | Send failed. `last_error` explains why. **Terminal in practice — not retried automatically.** See below. |
| `SKIPPED` | Deliberately not sent — template disabled at execution time, or the schedule anchor changed. `last_error` carries the reason. Terminal. |

⚠️ **`FAILED` does not self-heal.** The worker catches every exception and records it on the action instead of re-raising, so the queue job completes "successfully" and the messaging retry policy never fires. A `FAILED` action stays failed until an operator triggers a **new** manual send. Present it as a final state with a retry affordance, not as "retrying…".

(The retry policy does still cover infrastructure failures that occur before the send is attempted — e.g. the worker cannot reach the database to load the action.)

### 3.4 `DispatchStatus` — event-bus state (informational)

```ts
type DispatchStatus = "PENDING" | "CLAIMED" | "DISPATCHED" | "FAILED" | "DEAD";
```

Manual events are always created as `"DISPATCHED"` — see [§6.3](#63-how-to-recognise-a-manual-send-in-the-history).

### 3.5 `ScheduleAnchorType`

```ts
type ScheduleAnchorType = "occurred_at" | "future_business_time" | null;
```

Always `null` on manual actions — a manual send is immediate and has no anchor.

### 3.6 Reserved event name

```ts
const MANUAL_MESSAGE_EVENT_NAME = "order_manual_message";
```

This is the `event_name` of the synthetic event row a manual send produces. It is **not** in `OrderEventName` and must never be offered in the template picker — it is not a business event and no template can be configured for it.

---

## 4. Step 1 — Populate the template picker

### Request

```http
GET /api_v2/message_templates/?enable=true&limit=100
Authorization: Bearer <token>
```

Trailing slash is required.

**Query params** (all optional):

| Param | Type | Notes |
|---|---|---|
| `channel` | `MessageChannel` | Exact match |
| `event` | `OrderEventName` | Exact match |
| `enable` | boolean-ish | Exact match |
| `name` | string | Prefix match, case-insensitive |
| `client_id` | string | Exact match |
| `sort` | `"id_asc" \| "id_desc"` | Default `id_desc` |
| `limit` | number | Default `50` |
| `after_id` / `before_id` | number | Cursor pagination |

### Response

⚠️ **This is a normalized map, not an array.** Unlike the other two endpoints in this document, this one goes through the generic query serializer.

```jsonc
{
  "data": {
    "message_templates": {
      "byClientId": {
        "41": {
          "id": 41,
          "client_id": null,
          "event": "order_ready",
          "enable": true,
          "subject": "Your order is ready",
          "template": { "blocks": [], "footerButtons": [] },
          "ask_permission": false,
          "name": "Order ready — email",
          "channel": "email",
          "schedule_offset_value": null,
          "schedule_offset_unit": null
        }
      },
      "allIds": ["41"]
    },
    "message_templates_pagination": {
      "has_more": false,
      "next_cursor": { "after_id": 41 },
      "prev_cursor": { "before_id": 41 }
    }
  },
  "warnings": []
}
```

**Key derivation:** the map key is `String(client_id)` when `client_id` is set and non-empty, otherwise `String(id)`. `allIds` preserves sort order. Iterate `allIds` and look up `byClientId[id]` — do not use `Object.values()`, it loses ordering.

**When the result set is empty**, `pagination` is `{ "has_more": false, "next_cursor": null, "prev_cursor": null }`.

### Building the picker

One template row is one `(event, channel)` pair. To present the operator with a list of *messages* they can send, group by `event`:

```ts
interface TemplateOption {
  event: OrderEventName;
  label: string;                    // from any member template's `name`
  channels: SendableChannel[];      // enabled + sendable channels for this event
}

const SENDABLE: readonly SendableChannel[] = ["email", "sms"];

function buildOptions(map: MessageTemplateMap): TemplateOption[] {
  const byEvent = new Map<OrderEventName, TemplateOption>();

  for (const id of map.allIds) {
    const t = map.byClientId[id];
    if (!t.enable) continue;
    if (!SENDABLE.includes(t.channel as SendableChannel)) continue;

    const existing = byEvent.get(t.event);
    if (existing) {
      existing.channels.push(t.channel as SendableChannel);
    } else {
      byEvent.set(t.event, {
        event: t.event,
        label: t.name ?? t.event,
        channels: [t.channel as SendableChannel],
      });
    }
  }

  return [...byEvent.values()];
}
```

Only offer an event whose `channels` array is non-empty. `schedule_offset_value` / `schedule_offset_unit` are **ignored** for manual sends — do not surface them as "this will be sent in 2 hours", because it will not be.

`ask_permission` is currently **not read by any backend code**. Treat it as unused; do not build behavior on it without confirming with the backend first.

---

## 5. Step 2 — Send

### Request

```http
POST /api_v2/order_messages/send
Authorization: Bearer <token>
Content-Type: application/json
```

```ts
interface SendManualMessageRequest {
  order_ids: number[];              // required, 1..100, deduplicated server-side
  event: OrderEventName;            // required
  channels?: SendableChannel[];     // optional, defaults to ["email", "sms"]
  source_event_id?: number;         // optional, single-order requests only
}
```

| Field | Rules |
|---|---|
| `order_ids` | Non-empty array of integers. Booleans and numeric strings are rejected. Duplicates are removed, input order preserved. Max **100** per request. |
| `event` | Must be a member of `OrderEventName`. Whitespace is trimmed. |
| `channels` | Omit or `null` → both `email` and `sms` are attempted. If provided, must be a non-empty array of `"email"` / `"sms"`. Duplicates removed. |
| `source_event_id` | See [§5.3](#53-source_event_id--resending-a-specific-past-message). Only valid when `order_ids.length === 1`. |

Example:

```jsonc
{
  "order_ids": [12, 15, 88],
  "event": "order_ready",
  "channels": ["email", "sms"]
}
```

### Response — `200`

```ts
interface SendManualMessageResponse {
  request_id: string;               // uuid4 hex — correlates the socket frames (§9)
  event: OrderEventName;
  channels: SendableChannel[];      // channels that had an enabled template
  results: OrderSendResult[];       // one entry per requested order, input order preserved
}

type OrderSendResult = AcceptedResult | NotFoundResult;

interface AcceptedResult {
  order_id: number;
  status: "accepted";
  event_id: number;                 // the manual OrderEvent row id — use this to poll
  source_event_id: number | null;
  channels: Record<SendableChannel, ChannelResult>;
}

interface NotFoundResult {
  order_id: number;
  status: "not_found";              // no other fields present
}

type ChannelResult =
  | { status: "queued";  action_id: number }
  | { status: "failed";  action_id: number; detail: string }
  | { status: "skipped"; detail: string };
```

```jsonc
{
  "data": {
    "request_id": "b3f1c07a4e1d4f0b9e2a7c6d5f8a1b2c",
    "event": "order_ready",
    "channels": ["email"],
    "results": [
      {
        "order_id": 12,
        "status": "accepted",
        "event_id": 9912,
        "source_event_id": 883,
        "channels": {
          "email": { "status": "queued",  "action_id": 40113 },
          "sms":   { "status": "skipped", "detail": "No enabled sms template for event 'order_ready'." }
        }
      },
      { "order_id": 88, "status": "not_found" }
    ]
  },
  "warnings": []
}
```

### 5.1 ⚠️ `queued` is not `sent`

`"queued"` means the job was accepted onto the Redis/RQ `messaging` queue. Nothing has been delivered yet. The actual outcome — SMTP accepted, Twilio rejected, no phone number on the order — is only known later, on the **action row** ([§6](#6-step-3--poll-delivery-status)).

Copy this in the UI accordingly: *"3 messages queued"*, never *"3 messages sent"*.

`"failed"` at this stage is narrow: it means the job could not be enqueued at all (Redis unreachable). The action row is already marked `FAILED` when you receive this.

### 5.2 Partial success is normal

An order id that does not exist, or belongs to another team, yields `{"status": "not_found"}` for that entry only. **The request still returns `200`.** Never treat a `200` as "everything worked" — walk `results`.

Likewise `channels` is per-order and can mix `queued` and `skipped`: `skipped` means no enabled template exists for that `(event, channel)` pair, which is a configuration state, not an error.

### 5.3 `source_event_id` — resending a specific past message

Some templates render content taken from the **event payload**, not from the order. The reschedule templates are the clearest case: the "old → new" delivery time comes from `old_expected_arrival` / `new_plan_start` / `reason` on the original event.

To resend such a message faithfully, pass the id of the original `OrderEvent` (from the history in §6) as `source_event_id`. The backend copies that event's payload onto the manual event so the labels render identically.

- **Omitted** → the backend automatically uses the most recent event of that `event` name on the order, if one exists. This is the sensible default; you usually do not need this field.
- **No matching event at all** → the message is still sent, but payload-derived labels fall back gracefully (e.g. the reschedule template shows only the new time, no "old → new" comparison).
- **Provided but not matching** the given order + team + event name → `NotFound` (`414`).
- **Provided with more than one order** → `ValidationFailed` (`410`).

Use it when the operator resends from a specific row in the order's event history. Omit it for bulk sends.

### 5.4 Errors

Request-level failures reject the entire batch — nothing is queued.

| `code` | HTTP | Cause |
|---|---|---|
| `bad_request` | 410 | `order_ids` missing / empty / not integers / over 100 |
| `bad_request` | 410 | `event` missing or not a known `OrderEventName` |
| `bad_request` | 410 | `channels` empty, or contains anything other than `email` / `sms` |
| `bad_request` | 410 | `source_event_id` not an integer, or used with multiple orders |
| `bad_request` | 410 | **No enabled template exists for this event on any requested channel** |
| `bad_request` | 410 | Token carries no team context |
| `not_found` | 414 | `source_event_id` does not match the order / team / event |
| `forbidden` | 413 | Role is not `ADMIN` / `ASSISTANT`, or `app_scope` is not `admin` |

The "no enabled template on any channel" case is worth a specific UI message — it means the team has not configured this message at all, and the operator should be pointed at template settings.

---

## 6. Step 3 — Poll delivery status

### Request

```http
GET /api_v2/orders/{order_id}/events/
Authorization: Bearer <token>
```

Trailing slash is required. No query parameters are supported — this returns the **complete** event history for the order, newest first. There is no pagination and no filter, so it grows with the order's lifetime; fetch it for a detail view, not in a list.

### Response

```ts
interface OrderEventHistoryResponse {
  order_id: number;
  order_events: OrderEventRow[];    // ordered by occurred_at DESC, then id DESC
}

interface OrderEventRow {
  id: number;                       // matches `event_id` from the send response
  event_id: string | null;          // UUID string — a different field, do not confuse with `id`
  order_id: number;
  team_id: number | null;
  actor_id: number | null;          // user who triggered it; null for system events
  event_name: OrderEventName | "order_manual_message";
  payload: Record<string, unknown>; // {} when empty
  occurred_at: string | null;       // ISO 8601
  entity_type: string | null;       // "order"
  entity_id: string | null;
  entity_version: string | null;
  dispatch_status: DispatchStatus;
  dispatch_attempts: number;
  claimed_at: string | null;
  claimed_by: string | null;
  next_attempt_at: string | null;
  last_error: string | null;        // event-bus error, NOT the message send error
  relayed_at: string | null;
  actions: OrderEventActionRow[];   // ordered by created_at DESC, then id DESC
}

interface OrderEventActionRow {
  id: number;                       // matches `action_id` from the send response
  event_id: number;
  team_id: number | null;
  action_name: string;              // e.g. "manual_order_ready_email", "order_ready_sms"
  action_scope: string;             // "manual" for manual sends, "" for automatic
  payload: Record<string, unknown>; // {} when empty
  status: ActionStatus;
  attempts: number;
  last_error: string | null;        // ← the send failure reason
  scheduled_for: string | null;     // always null on manual sends
  enqueued_at: string | null;
  processed_at: string | null;
  schedule_anchor_type: ScheduleAnchorType;
  schedule_anchor_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}
```

⚠️ `OrderEventRow.id` (number) and `OrderEventRow.event_id` (UUID string) are **both present and different**. The `event_id` returned by the send endpoint is the numeric `id`. `OrderEventActionRow.event_id` is also the numeric one. Only the event row's own `event_id` field is a UUID.

### 6.1 Reading a manual send's outcome

Given `event_id: 9912` and `action_id: 40113` from the send response:

```ts
const event = res.order_events.find(e => e.id === 9912);
const action = event?.actions.find(a => a.id === 40113);

switch (action?.status) {
  case "PENDING": return "Sending…";
  case "SUCCESS": return `Sent ${action.processed_at}`;
  case "FAILED":  return `Failed: ${action.last_error}`;
  case "SKIPPED": return `Not sent: ${action.last_error}`;
}
```

`last_error` is populated on both `FAILED` and `SKIPPED`, and is truncated to 3000 characters. It is raw backend text — surface it in a details/tooltip affordance, not as primary copy.

Common values:

| `status` | `last_error` | Meaning for the operator |
|---|---|---|
| `FAILED` | `Order has no client email` | Order is missing the contact detail |
| `FAILED` | `Order has no valid recipient phone number` | Same, for SMS |
| `FAILED` | `Missing team context for email send` | Data integrity problem — escalate |
| `SKIPPED` | `Email template is missing or disabled at execution time` | Template was disabled between queueing and sending |
| `FAILED` | *(SMTP / Twilio provider text)* | Provider rejected it |

### 6.2 Prefer the socket frames — polling is the fallback

Manual sends push realtime frames (see [§9](#9-realtime-socket-frames)). Use those as the primary status mechanism; the history endpoint is for the initial render, for reconnects, and as a fallback if the socket is down.

If you do poll — sends are typically sub-second once a worker picks the job up, but provider latency can stretch it:

```
poll at 2s, 5s, 10s, 20s  → stop as soon as every tracked action leaves
                             PENDING, or on the last attempt
```

All three of `SUCCESS`, `FAILED` and `SKIPPED` are terminal — stop polling on any of them. Only `PENDING` is worth another poll. If an action is still `PENDING` after the last attempt, the queue is backed up or no worker is running; show "still queued" rather than an error.

For a bulk send across N orders, this is N requests. Keep bulk-send UI to a summary ("42 queued") and only poll per-order detail when the operator opens a specific order.

### 6.3 How to recognise a manual send in the history

A manual send appears as **its own event row**, never nested under the original business event. Identify it by any of:

```ts
const isManual =
  event.event_name === "order_manual_message" ||
  action.action_scope === "manual" ||
  action.action_name.startsWith("manual_");
```

The event row carries the operator context in `payload.manual`:

```jsonc
{
  "id": 9912,
  "event_name": "order_manual_message",
  "dispatch_status": "DISPATCHED",
  "actor_id": 41,
  "payload": {
    // ...any payload copied from the source event, verbatim...
    "manual": {
      "template_event":  "order_ready",   // the template actually sent
      "channels":        ["email"],
      "requested_by":    41,              // user id
      "source_event_id": 883              // or null
    }
  },
  "actions": [
    {
      "id": 40113,
      "action_name": "manual_order_ready_email",
      "action_scope": "manual",
      "status": "SUCCESS",
      "payload": {
        "template_event":  "order_ready",
        "channel":         "email",
        "manual":          true,
        "requested_by":    41,
        "source_event_id": 883
      }
    }
  ]
}
```

**Always render the label from `payload.manual.template_event`, not from `event_name`.** `event_name` is the generic `"order_manual_message"`; the operator wants to see *"Order ready — resent by David"*.

Note that keys copied from the source event sit alongside `manual` at the top level of `payload`. Read manual metadata only from `payload.manual`.

`dispatch_status` is `"DISPATCHED"` from creation and `last_error` on the event row stays `null` — the manual event never goes through the event bus by design, so neither field tells you anything about delivery. Delivery lives on the **action**.

---

## 7. End-to-end example

```ts
async function resendOrderReady(orderIds: number[]) {
  const res = await api.post<SendManualMessageResponse>(
    "/api_v2/order_messages/send",
    { order_ids: orderIds, event: "order_ready", channels: ["email", "sms"] },
  );

  const accepted = res.data.results.filter(
    (r): r is AcceptedResult => r.status === "accepted",
  );
  const missing = res.data.results.filter(r => r.status === "not_found");

  const queued = accepted.flatMap(r =>
    Object.entries(r.channels)
      .filter(([, c]) => c.status === "queued")
      .map(([channel, c]) => ({
        orderId: r.order_id,
        eventId: r.event_id,
        actionId: (c as { action_id: number }).action_id,
        channel,
      })),
  );

  toast(`${queued.length} message(s) queued`);
  if (missing.length) {
    toast.warn(`${missing.length} order(s) not found`);
  }

  return queued; // feed into the poller from §6.2
}
```

---

## 8. What does **not** exist yet

Be aware of these before designing the UI — none of them are available today.

1. **No message-body preview endpoint.** You cannot ask the backend "what will order 12 receive if I send `order_ready`?". Rendering happens inside the worker at send time, using the team's SMTP/Twilio config, the order, the event payload, and the label resolvers. The raw `template` / `subject` JSON from §4 is a block structure with unresolved label placeholders — rendering it client-side would duplicate a non-trivial backend resolver and drift from it. If the operator needs a true preview, ask the backend team for a dedicated render endpoint.

2. **No custom recipient override.** Messages always go to the order's own contact details. The one exception is the pre-existing client-form-link flow, which is a separate endpoint.

3. **No free-text / ad-hoc message.** The operator can only send an existing configured template.

4. **No aggregated "batch finished" signal.** There is no frame that fires once when every message in a request has settled, and no persisted notification for a completed bulk send. Track completion client-side by counting `order_message.updated` frames against `total_actions` from the dispatched frame. If an operator navigates away mid-send, they will not be told the batch finished.

5. **No route-plan equivalent.** This covers order messaging only. Route-plan messages remain automatic.

6. **`ask_permission` on `MessageTemplate` is not wired to anything.** It is serialized but never read by backend logic.

---

## 9. Realtime socket frames

Manual sends publish two frames. Both arrive on the existing `realtime:event` server event, inside the standard business-event envelope, on the **`team_admin` channel only** (`app_scopes: ["admin"]`). Drivers never receive them.

You must already be subscribed to `team_admin` via `realtime:subscribe` — no new channel or subscription is introduced.

### 9.1 Envelope

```ts
interface BusinessEventEnvelope<TPayload> {
  event_id: string;                 // uuid4, per frame
  event_name: string;
  version: string;                  // "1"
  occurred_at: string;              // ISO 8601
  team_id: number | null;
  entity_type: string;
  entity_id: number | null;
  app_scopes: string[];             // ["admin"]
  payload: TPayload;
}
```

Every payload also carries a `notification_preview: { kind, title, description }`. It is a display hint only — **no notification row is persisted** for message sends, deliberately, so a 100-order batch does not bury the notification feed.

### 9.2 `order_message.dispatched` — one per send request

Emitted synchronously by the send endpoint, after every action row is persisted but **before any of them is queued**. That ordering is deliberate: it guarantees this frame always reaches you before any `order_message.updated` frame for the same request, even on a large batch where the first order is delivered while the last is still being queued.

`entity_type` is `"order_message_request"` and `entity_id` is `null`.

```ts
interface OrderMessageDispatchedPayload {
  request_id: string;               // matches the HTTP response
  template_event: OrderEventName;
  channels: SendableChannel[];
  requested_by: number | null;      // user id
  total_actions: number;            // progress-bar denominator
  orders: Array<{
    order_id: number;
    event_id: number;
    actions: Array<{
      action_id: number;
      channel: SendableChannel;
      status: "PENDING";            // always — nothing is queued yet
    }>;
  }>;
  not_found_order_ids: number[];
}
```

Skipped channels are **absent** from `orders[].actions` — they never produced an action. The request-level `channels` field already tells you which channels the team has configured.

If an action cannot be queued at all (Redis unreachable), it arrives as a normal `order_message.updated` frame with `status: "FAILED"`, so `total_actions` always settles.

For the operator who triggered the send this duplicates the HTTP response; its real value is other operators' sessions, which learn a batch started.

### 9.3 `order_message.updated` — one per settled message

Emitted by the worker when an action reaches `SUCCESS`, `FAILED`, or `SKIPPED`. Not emitted for `PENDING`. `entity_type` is `"order"` and `entity_id` is the order id, so order-scoped listeners can route it directly.

```ts
interface OrderMessageUpdatedPayload {
  request_id: string | null;
  order_id: number | null;
  event_id: number;
  action_id: number;
  template_event: OrderEventName;
  channel: SendableChannel | null;
  status: "SUCCESS" | "FAILED" | "SKIPPED";
  last_error: string | null;
  processed_at: string | null;      // ISO 8601
}
```

```jsonc
{
  "event_name": "order_message.updated",
  "entity_type": "order",
  "entity_id": 12,
  "app_scopes": ["admin"],
  "payload": {
    "request_id": "b3f1c07a…",
    "order_id": 12, "event_id": 9912, "action_id": 40113,
    "template_event": "order_ready", "channel": "email",
    "status": "FAILED", "last_error": "Order has no client email",
    "processed_at": "2026-07-24T11:02:31+00:00",
    "notification_preview": { "kind": "order_message.updated", "title": "Message failed", "description": "order_ready · email" }
  }
}
```

### 9.4 Consuming them

```ts
socket.on("realtime:event", (envelope: BusinessEventEnvelope<unknown>) => {
  switch (envelope.event_name) {
    case "order_message.dispatched": {
      const p = envelope.payload as OrderMessageDispatchedPayload;
      startBatch(p.request_id, p.total_actions);
      break;
    }
    case "order_message.updated": {
      const p = envelope.payload as OrderMessageUpdatedPayload;
      applyActionStatus(p.order_id, p.action_id, p.status, p.last_error);
      if (p.request_id) tickBatch(p.request_id);   // settled / total_actions
      break;
    }
  }
});
```

### 9.5 Guarantees and limits

- **Volume is one frame per settled message.** A 100-order × 2-channel send produces 1 dispatched frame and up to 200 updated frames, spread over the send. There is no coalescing today.
- **Frames are not replayed.** A client that reconnects mid-send misses everything sent while disconnected. On reconnect, refetch `GET /api_v2/orders/{order_id}/events/` for any order still shown as pending — that endpoint is always authoritative.
- **Delivery is best-effort.** A socket failure is logged and swallowed so it can never fail or mis-mark a send that already happened. Treat the frames as an accelerator over the history endpoint, never as the system of record.
- **`dispatched` always precedes its `updated` frames** for the same `request_id` (see §9.2). Beyond that, ordering **between** actions is not guaranteed — always key updates by `action_id` rather than assuming arrival order.
- **Automatic (non-manual) sends do not emit these frames.** They continue to fan out as `order.updated` / `order.state_changed` exactly as before — this feature changed nothing for them.

---

## 10. Backend reference

| Concern | File |
|---|---|
| Endpoint | `routers/api_v2/order_messaging.py` |
| Command | `services/commands/order/messaging/send_manual_message.py` |
| Validation rules & constants | `services/domain/messaging/manual_send.py` |
| Send workers | `services/infra/tasks/order/send_email.py`, `send_sms.py` |
| Action → task routing | `services/infra/events/action_dispatch.py` |
| History serializer | `services/queries/order/get_order_event_history.py` |
| Template serializer | `services/queries/content_templates/messages/serialize_message_templates.py` |
| Event name enum | `services/domain/order/order_events.py` |
| Error → HTTP mapping | `routers/http/response.py` |

Questions or a change in shape: ping the backend before working around anything in §8.
