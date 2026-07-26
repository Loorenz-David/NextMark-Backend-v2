# Route Plan Schedule Date on Client Form — Backend Handoff

## Goal

Render the **route plan schedule date** of an order in the header of the customer-facing
client form. The date is the `RoutePlan` schedule (a single date, or a range) that the order
is assigned to — **not** the delivery window (that is a different value and is out of scope here).

The frontend needs this value delivered inside the **existing** public client-form projection so it
can render it in the form header. This is a **single, additive backend change** — no new
endpoint, no model change, no migration.

> Scope note: there are two client forms in the product. Only **one** needs a backend change.
> - **Customer/token form** (`external-operations-app`, opened via `GET /public/client-form/<token>`) → **needs this backend change.**
> - **Admin counter/linked-device form** (`admin-app`) → **no backend change.** It receives the date
>   from the till over the existing external-form socket relay, which already forwards `request_data`
>   verbatim. Do not touch the socket handler for this.

---

## The single change

**File:** `Back_end/Delivery_app_BK/services/commands/order/client_form/get_client_form.py`
**Function:** `get_client_form_data(token: str) -> dict` (currently lines ~19–40)

This function already loads the full `Order` ORM instance via `validate_and_get_order(token)` and
assembles the public projection dict. Add **one key** — `route_plan_schedule` — to the returned dict.

### Data source

- An `Order` links **directly** to its route plan: `order.route_plan` (FK `route_plan_id`,
  also exposed via the `delivery_plan` synonym). Model: `RoutePlan`, table `route_plan`
  (`Back_end/Delivery_app_BK/models/tables/route_operations/route_plan/route_plan.py`).
- The schedule fields on `RoutePlan`:
  - `date_strategy` — `"single"` or `"range"` (non-null)
  - `start_date` — `UTCDateTime`, **nullable**
  - `end_date` — `UTCDateTime`, **nullable**
- **Both the plan link and the dates are nullable.** An order may be unassigned
  (`route_plan_id` is nullable, `ondelete="SET NULL"`), and even an assigned plan may have null dates.
  The response must guard all three cases and emit `null`.

### Shape to emit (mirror the existing plan serializers)

Use the exact same three-key shape that `serialize_plans`
(`services/queries/route_plan/serialize_plan.py`) already emits, so nothing new is invented:

```python
{
    "date_strategy": <"single" | "range" | None>,
    "start_date":    <ISO-8601 string or None>,
    "end_date":      <ISO-8601 string or None>,
}
```

### Suggested implementation

```python
def get_client_form_data(token: str) -> dict:
    order = validate_and_get_order(token)
    # ... existing team / items assembly ...

    plan = order.route_plan  # nullable; direct FK, no extra query needed

    return {
        "order_scalar_id": order.order_scalar_id,
        "reference_number": order.reference_number,
        "external_source": order.external_source,
        "team_timezone": team.time_zone if team is not None else None,
        "items": items,
        "expires_at": order.client_form_token_expires_at.isoformat(),
        # NEW — route plan schedule date for the form header.
        "route_plan_schedule": (
            {
                "date_strategy": plan.date_strategy,
                "start_date": plan.start_date.isoformat() if plan.start_date else None,
                "end_date": plan.end_date.isoformat() if plan.end_date else None,
            }
            if plan is not None
            else None
        ),
        "config": build_public_client_form_config(order.team_id),
    }
```

Do not change the rest of the dict. `route_plan_schedule` is purely additive; the frontend
treats a missing/`null` value as "no scheduled date" and simply renders nothing.

---

## Important behavioral note for the frontend (no action needed, context only)

For `date_strategy == "single"` the model auto-populates `end_date` to end-of-day of the same
calendar date. So a single-date plan will still return a populated `end_date`. **That is fine** —
the frontend decides single-vs-range from `date_strategy` (falling back to same-calendar-day
detection), so please make sure `date_strategy` is included exactly as stored. Do **not** null out
`end_date` for single-strategy plans; send it as-is.

---

## Out of scope — do NOT change these

- `GET /client_form_config/projection`
  (`services/queries/client_form_config/get_client_form_projection.py`) — team-scoped config only,
  has no order context. Leave it alone.
- The external-form socket handlers
  (`sockets/handlers/external_form.py`, `handle_external_form_request_user`) — the admin form's
  date travels through the till's `request_data` verbatim; no server enrichment is wanted.
- The `OrderDeliveryWindow` model / `order_delivery_window` table — that is the delivery window,
  a different value, explicitly not what we are rendering.

---

## Acceptance criteria

1. `GET /public/client-form/<token>` response includes a top-level `route_plan_schedule` key.
2. When the order has an assigned plan with dates:
   `route_plan_schedule = { "date_strategy": "...", "start_date": "<ISO>", "end_date": "<ISO>" }`.
3. When the order has **no** plan: `route_plan_schedule = null`.
4. When the plan exists but a date column is null: that field is `null` (never a crash).
5. No change to any other key in the response, no new endpoint, no migration.
6. Existing client-form tests still pass; add coverage for the assigned / unassigned / null-date cases.
