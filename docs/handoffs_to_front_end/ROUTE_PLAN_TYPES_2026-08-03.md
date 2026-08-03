# Route Plan Types — Backend → Frontend Handoff

Created: 2026-08-03
Scope: `route_plan` gains an explicit `plan_type`; international shipping and store pickup become creatable plans; order moves now cross planning domains
Backend branch: `feat/route-plan-plan-type` (6 commits)

---

## What Changed and Why

A route plan had no type. Which planning domain owned it could only be guessed from
which child rows happened to exist, so nothing could tell whether an order belonged on
the plan it was sitting on. That produced four concrete failures:

- Assigning an order to a plan **force-rewrote** its `order_plan_objective` to
  `local_delivery`, whatever it had been, with no way back.
- Creating an order with an explicit objective onto a mismatched plan was accepted, and
  because the receiving domain has no handler, **no route stop was ever built** — the
  order sat on the plan invisible to its route.
- Editing an assigned order through the order form **silently cleared** its objective.
- Route optimization loaded *every* order on a plan regardless of type, so a foreign
  order became a shipment and got routed to a vehicle.

`route_plan.plan_type` now states the domain explicitly, using the **same value space as
`order_plan_objective`**:

```
"local_delivery" | "international_shipping" | "store_pickup"
```

It is set at creation and cannot be changed afterwards.

---

## 1. `plan_type` Now Appears on Plan Payloads

`plan_type` is present on every route plan the API returns. For all existing data the
value is `"local_delivery"` — every plan that existed before this change was a route
operations plan and was backfilled as one.

**List / detail shape** (`GET /api_v2/route_plans/`):

```json
{
  "id": 956,
  "client_id": "route_plan_...",
  "label": "Q4 Overseas",
  "plan_type": "international_shipping",
  "date_strategy": "single",
  "start_date": "2026-10-01T00:00:00+00:00",
  "end_date": "2026-10-01T23:59:59.999999+00:00",
  "created_at": "2026-08-03T06:53:30.777562+00:00",
  "updated_at": "2026-08-03T06:53:30.777568+00:00",
  "state_id": 1,
  "route_groups_count": 0,
  "total_items": 0,
  "total_volume": 0.0,
  "total_weight": 0.0,
  "total_orders": 0
}
```

Note `route_groups_count: 0` — non-local plans have no route groups at all. Any UI that
assumes at least one route group per plan needs a guard.

### ⚠️ `plan_type` changed meaning on route-solution payloads

This field already existed on route-solution payloads and socket events, but it was
**hardcoded to the literal string `"route_plan"`** for every plan. It now carries the
plan's real type.

| Payload | Before | After |
|---|---|---|
| `serialize_route_solution` / `_partial` | `"route_plan"` | `"local_delivery"` (real type) |
| socket `route_group.updated` | `"route_plan"` | real type |
| socket `route_solution.created` / `.updated` | `"route_plan"` | real type |
| socket `route_plan.created` / `.updated` / `.deleted` | `"route_plan"` | real type |

We grepped the frontend and found **no comparison against `"route_plan"`**, so nothing
should break. `planMeta.ts` already types the field as `RoutePlanObjective`, which is now
accurate rather than aspirational.

The driver app's `plan_type` (in `routes.dto.ts` → `mapRouteDtoToRouteRecord.ts`) was
reading a column that did not exist and therefore always received `null`. It now receives
`"local_delivery"`. Nothing in the driver app reads the value, so no change is required —
see `driver_app_plan_type_handoff` for the follow-up on typing it properly.

---

## 2. Creating International Shipping Plans

```
POST /api_v2/international_shipping_plans/
```

Roles: `ADMIN`, `ASSISTANT`. Payload follows the standard `fields` array convention.

**Request**

```json
{
  "fields": [
    {
      "label": "Q4 Overseas",
      "start_date": "2026-10-01",
      "end_date": "2026-10-05",
      "carrier_name": "DHL Express",
      "order_ids": [1201, 1202],
      "client_id": "optional-idempotency-key"
    }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `label` | ✅ | |
| `start_date` | ✅ | ISO date or datetime |
| `end_date` | — | Defaults to end-of-day of `start_date` |
| `date_strategy` | — | `"single"` (default) or `"range"` |
| `carrier_name` | — | Free string, the domain-specific field |
| `order_ids` | — | Orders to move onto the plan on creation |
| `client_id` | — | Auto-generated when omitted |

**Response**

```json
{
  "created": [
    {
      "route_plan": {
        "id": 953,
        "client_id": "international_shipping_plan_...",
        "label": "Q4 Overseas",
        "plan_type": "international_shipping",
        "date_strategy": "single",
        "start_date": "2026-10-01T00:00:00+00:00",
        "end_date": "2026-10-01T23:59:59.999999+00:00",
        "created_at": "...",
        "updated_at": "...",
        "state_id": 1,
        "item_type_counts": null,
        "total_items": 0,
        "total_volume": 0.0,
        "total_weight": 0.0,
        "total_orders": 0
      },
      "international_shipping_plan": {
        "id": 2,
        "client_id": "international_shipping_plan_...",
        "route_plan_id": 953,
        "carrier_name": "DHL Express"
      }
    }
  ]
}
```

The domain row is a **separate entity** keyed to `route_plan_id`, one per plan. The plan
holds the schedule and the orders; the child holds what is specific to shipping.

---

## 3. Creating Store Pickup Plans

```
POST /api_v2/store_pickup_plans/
```

**Request**

```json
{
  "fields": [
    {
      "label": "Counter A",
      "start_date": "2026-10-01",
      "pickup_location": {
        "street_address": "12 Retail Rd",
        "country": "CO",
        "coordinates": { "lat": 4.6, "lng": -74.1 }
      },
      "assigned_user_id": 7,
      "order_ids": [1203]
    }
  ]
}
```

Same shell fields as above, plus:

| Field | Required | Notes |
|---|---|---|
| `pickup_location` | — | Must satisfy the **address schema** — see below |
| `assigned_user_id` | — | Integer FK to `user`. Must be an integer, not a string |

**`pickup_location` must match the shared address schema**, the same one used by
`client_address`. Required keys: `street_address`, `country`, `coordinates` (with `lat`
and `lng` as numbers). Additional properties are rejected. Optional: `postal_code`,
`city`.

Sending a partial address returns:

```
Invalid address in field 'pickup_location': 'street_address' is a required property
```

**Response**

```json
{
  "created": [
    {
      "route_plan": { "...": "same shape as above", "plan_type": "store_pickup" },
      "store_pickup_plan": {
        "id": 2,
        "client_id": "store_pickup_plan_...",
        "route_plan_id": 957,
        "pickup_location": { "street_address": "12 Retail Rd", "country": "CO", "coordinates": { "lat": 4.6, "lng": -74.1 } },
        "assigned_user_id": null
      }
    }
  ]
}
```

---

## 4. Payload Fields These Endpoints Reject

Route groups and zones belong to route operations. If a payload copied from the local
delivery create form includes any of `zone_ids`, `route_group_defaults`, or
`route_group_id`, the request fails with an explicit message:

```
International shipping plans do not have route groups or zones. Unsupported fields: ['zone_ids'].
```

Also rejected:

| Field | Message |
|---|---|
| `plan_type` | `plan_type is implied by this endpoint and cannot be set on the payload.` |
| `state_id` | `state_id is not allowed on create. New plans always start as OPEN.` |
| anything unknown | `Unexpected fields in create payload: [...]` |

---

## 5. What Happens Behind the Scenes on an Order Move

This is the part worth understanding, because a move is no longer a simple pointer update.

The move endpoints are unchanged:

```
PATCH /api_v2/order_assignments/orders/<order_id>/plan/<plan_id>
PATCH /api_v2/order_assignments/plans/<plan_id>/batch
PATCH /api_v2/order_assignments/orders/<order_id>/unassign-plan
```

They now work with **any** plan type as the destination. When an order moves:

1. **The order adopts the destination plan's type.** `order_plan_objective` is set from
   `plan.plan_type`. The frontend already models this — `orderPlanAssignmentOptimistic.ts`
   sets `order_plan_objective: params.planType` optimistically, which is now exactly what
   the backend does.

2. **The domain it is leaving tears down what it built.** Leaving a local delivery plan
   deletes the order's `RouteSolutionStop` rows and resequences the remaining stops on
   those routes. International shipping and store pickup build nothing today, so leaving
   them is a no-op.

3. **The domain it is joining builds its own artifacts.** Joining a local delivery plan
   creates one stop per route solution in the destination route group. Joining the other
   two creates nothing yet.

4. **`route_group_id` is set only for local delivery.** Moving to an international or
   store pickup plan sets it to `null`.

### Observed behaviour, verified against real data

An order with 3 stops (one per route-solution variant in its group):

```
start (local delivery)     objective=local_delivery         plan= 32  group=59    stops=3
-> international           objective=international_shipping plan=949  group=None  stops=0
-> store pickup            objective=store_pickup           plan=950  group=None  stops=0
-> back to local           objective=local_delivery         plan= 32  group=59    stops=3
```

The round trip rebuilds all 3 stops on the same 3 route solutions.

**Two caveats on returning to local delivery:**

- **Stop position is not preserved.** The order rejoins at the tail of the route, not its
  previous position. Nothing records where it used to sit, and the route needs
  re-optimizing after a move anyway.
- **The route group is inferred, not restored.** Without an explicit `route_group_id`, the
  destination group is resolved from the order's zone assignment, falling back to the
  no-zone group. If the zone assignment changed while the order was away, it can land in a
  different group than it left. This is pre-existing behaviour for every move.

### Response bundle

Unchanged in shape. For a move involving local delivery it still carries the rebuilt
artifacts so you do not need to refetch:

```
["order", "order_stops", "plan_totals", "route_solution", "state_changes"]
```

For a move between two non-local plans, `order_stops` and `route_solution` are absent —
there is nothing to report.

### `route_group_id` is rejected for non-local destinations

Passing `route_group_id` when the destination is not a local delivery plan:

```
route_group_id is only valid for local delivery route plans.
```

---

## 6. `order_plan_objective` Is Now Owned by the Plan

**This is the behavioural change most likely to affect existing frontend code.**

While an order **is assigned to a plan**, its objective belongs to the plan. Moving the
order is the only way to change it.

| Situation | Result |
|---|---|
| Order unassigned, any objective sent | ✅ Written normally |
| Order assigned, field omitted | ✅ No-op |
| Order assigned, field sent as `null` | ✅ **Ignored** — treated as "nothing to assert" |
| Order assigned, same value repeated | ✅ No-op |
| Order assigned, **different** value sent | ❌ Rejected |

Rejection message:

```
order_plan_objective cannot be changed while the order is assigned to a route plan.
Move the order to a plan of the target type instead.
```

### The `null` case matters to you specifically

`orderForm.normalize.ts` currently sends:

```ts
order_plan_objective:
  state.delivery_plan_id == null
    ? toNullableString(state.order_plan_objective)
    : null,
```

That `null` for assigned orders was **clearing the objective on every edit** — a live bug
before this change, not something introduced by it. The backend now ignores a `null` on an
assigned order and never writes it, so the current frontend code is safe as-is. No change
is required, though sending the field only when it is meaningful would be cleaner.

The objective selector is already hidden for assigned orders in `OrderFormFields.tsx`,
which matches the new rule exactly.

### On create

Creating an order with a `delivery_plan_id` derives the objective from that plan. Sending
an objective that contradicts the plan is rejected:

```
Order objective 'international_shipping' does not match the 'local_delivery' plan it is being assigned to.
```

Omit `order_plan_objective` when creating an order onto a plan and it will be filled in
correctly.

---

## 7. Filtering Plans by Type

`GET /api_v2/route_plans/` accepts a `plan_type` filter, as a **single value or a list**.

```
?plan_type=international_shipping
?plan_type[]=local_delivery&plan_type[]=international_shipping
```

or inside the `filters` object of a POST-style query payload:

```json
{ "filters": { "plan_type": ["local_delivery", "store_pickup"] } }
```

- **Omitting it returns every plan type** — existing callers are unaffected.
- `route_plan_stats` respects the filter, so counts match the filtered list.
- An unrecognised value is **rejected**, not silently empty:

```
Invalid plan_type: local-delivery. Allowed values: ['international_shipping', 'local_delivery', 'store_pickup'].
```

Verified against real data:

| Filter | Result |
|---|---|
| none | 202 |
| `local_delivery` | 201 |
| `international_shipping` | 1 |
| `["local_delivery", "international_shipping"]` | 202 |
| `store_pickup` | 0 |

> Note: `plan_type` was already being forwarded to this query before this change but was
> never consumed, so any filter you were sending was silently ignored and returned
> everything. It is honoured now — check existing call sites.

---

## 8. Other Rejections to Handle

### Plan type is immutable

`PATCH /api_v2/route_plans/` with `plan_type` in the fields:

```
plan_type cannot be changed after a plan is created.
```

Previously this field was silently dropped. It now fails loudly. The legacy keys
`local_delivery`, `international_shipping`, `store_pickup` are still dropped silently for
backwards compatibility.

### Optimization is local delivery only

Requesting a route optimization for a non-local plan:

```
Route optimization is only available for local delivery plans. This plan is 'store_pickup'.
```

Hide or disable optimize actions for plans whose `plan_type` is not `local_delivery`.

---

## 9. Frontend Checklist

- [ ] Read `plan_type` from plan payloads instead of inferring the domain
- [ ] Guard any code that assumes a plan has ≥1 route group (`route_groups_count` can be `0`)
- [ ] Build create forms for the two new plan types against the endpoints in §2 and §3
- [ ] Use the address-schema shape for `pickup_location` (`street_address`, `country`, `coordinates`)
- [ ] Pass `plan_type` (single or list) when scoping a plan workspace; audit any existing `plan_type` filter call sites that were silently ignored
- [ ] Hide/disable route optimization for non-local plans
- [ ] Hide/disable route-group pickers when the destination plan is not local delivery
- [ ] Surface the objective-mismatch and immutability errors as user-facing messages
- [ ] Expect `order_stops` / `route_solution` to be absent from move bundles between non-local plans

## Not Changed

- Order move endpoints, request shapes, and response bundle keys
- Route group, route solution, and stop endpoints
- Driver app payloads (`plan_type` value changes from `null` to `"local_delivery"`, unread)
- Anything about how local delivery plans are created or optimized
