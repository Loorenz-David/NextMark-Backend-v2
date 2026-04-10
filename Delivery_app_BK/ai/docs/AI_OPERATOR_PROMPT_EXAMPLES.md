# AI Operator Prompt Examples

Date: 2026-04-01
Scope: Current toolset (18 registered tools, through Phase 5)

This file provides practical examples of typical prompts the AI Logistics Operator can handle now, plus the expected answer style.

## How to Read These Examples

- User prompt: natural language input from an operator.
- AI behavior: which tool(s) the agent should call and why.
- Typical final answer: concise narrative the assistant should return (not raw DB dumps).
- Notes: constraints or prerequisites.

---

## 1) Daily Operations Overview

User prompt:
"Give me a quick overview of today's operations."

AI behavior:
- Call `get_operations_dashboard` (date defaults to today if omitted).
- Summarize plan count, order volume, and notable alerts.

Typical final answer:
"Today we have 4 active plans and 126 total orders. Two plans are still Open and one plan has no route groups yet. Priority action: materialize route groups for the ungrouped plan before optimization."

Notes:
- Prefer short strategic summary with risks and next action.

---

## 2) Plan Health Check

User prompt:
"How is plan 42 doing?"

AI behavior:
- Call `get_plan_snapshot(plan_id=42)`.
- Explain readiness, unzoned orders, unoptimized groups, and major warnings.

Typical final answer:
"Plan 42 is in Ready state with 31 orders across 3 route groups. There are 2 unzoned orders in the default bucket and 1 route group is still unoptimized. Main risk is delayed dispatch for that unoptimized group."

Notes:
- Use the plan label/state from tool output when available.

---

## 3) Route Group Deep Check

User prompt:
"Inspect route group 103 and tell me if it is safe to dispatch."

AI behavior:
- Call `get_route_group_snapshot(route_group_id=103)`.
- Highlight active route, violations, ETA staleness, and driver assignment.

Typical final answer:
"Route group 103 has an active optimized route and assigned driver, but there are 2 constraint violations and stale ETAs on 3 stops. I recommend refreshing ETAs before dispatch."

Notes:
- Do not claim dispatch-safe unless constraints and stale ETA risk are clear.

---

## 4) Find Orders by State

User prompt:
"Show me unassigned confirmed orders."

AI behavior:
- Call `list_orders(scheduled=false, state='Confirmed')`.
- Return a compact summary and mention count/has_more.

Typical final answer:
"Found 18 confirmed unscheduled orders. Most are dropoff operations and 6 are in high-density zones. I can assign them to a plan when you confirm the destination plan id."

Notes:
- This is often a prerequisite before mutation.

---

## 5) List Candidate Plans

User prompt:
"List open plans covering tomorrow."

AI behavior:
- Call `list_plans(state='Open', covers_date='YYYY-MM-DD')`.
- Provide concise comparison by order load/group count.

Typical final answer:
"I found 3 open plans covering tomorrow: Plan 77 (42 orders), Plan 81 (19 orders), and Plan 82 (empty shell). Plan 82 is safest if you want to avoid mixing workloads."

Notes:
- Suggest a decision path when multiple candidates exist.

---

## 6) Assign Orders to Plan

User prompt:
"Assign orders 501, 505, 510 to plan 82."

AI behavior:
- If IDs were not previously confirmed, call `list_orders` first to validate targets.
- Call `assign_orders_to_plan(order_ids=[...], plan_id=82)`.
- Return mutation result with updated count.

Typical final answer:
"Done. Assigned 3 orders to plan 82. They were moved into the plan's default (no-zone) route group."

Notes:
- Safety rule: confirm targets before mutation when uncertain.

---

## 7) Assign Orders to Specific Route Group

User prompt:
"Move orders 501 and 505 to route group 214."

AI behavior:
- Confirm route group exists (typically via `list_route_groups(plan_id=...)` if needed).
- Call `assign_orders_to_route_group(order_ids=[501,505], route_group_id=214)`.

Typical final answer:
"Done. Assigned 2 orders to route group 214 in plan 82."

Notes:
- Tool resolves parent plan automatically from route group.

---

## 8) Transition Order State

User prompt:
"Set orders 501, 505, 510 to Ready."

AI behavior:
- Validate state name against domain map.
- Call `update_order_state(order_ids=[...], state='Ready')`.

Typical final answer:
"Updated 3 orders to state \"Ready\"."

Notes:
- Use state names, never numeric state IDs.

---

## 9) Create Plan with Initial Zones

User prompt:
"Create a plan called Morning North for 2026-04-02 and materialize zones 11 and 12."

AI behavior:
- Call `create_plan(label='Morning North', start_date='2026-04-02', zone_ids=[11,12])`.
- Summarize created plan and route group count.

Typical final answer:
"Created plan \"Morning North\" (id=96) for 2026-04-02 with 2 route groups."

Notes:
- New plans start as Open.

---

## 10) Materialize Route Groups Later

User prompt:
"For plan 96, create route groups for zones 13 and 14."

AI behavior:
- Call `materialize_route_groups(plan_id=96, zone_ids=[13,14])`.
- Report created-or-existing count (idempotent behavior).

Typical final answer:
"Materialized 2 route groups for plan 96."

Notes:
- Existing zone groups are reused, not duplicated.

---

## 11) Search Item Types

User prompt:
"Find item types starting with 'frag'."

AI behavior:
- Call `search_item_types(q='frag')`.
- Return concise count and a short sample by name.

Typical final answer:
"Found 4 item types matching \"frag\": Fragile Box, Fragile Envelope, Fragile Electronics, Fragile Glass."

Notes:
- Prefix search behavior.

---

## 12) Add Items to Existing Order

User prompt:
"Add two items to order 501: FR-001 fragile box quantity 2 weight 800, and FR-002 fragile envelope quantity 1 weight 200."

AI behavior:
- Optionally confirm order exists via `list_orders`.
- Call `add_items_to_order(order_id=501, items=[...])`.
- Report created_count and recomputation status.

Typical final answer:
"Added 2 items to order 501. Order and related plan totals were recomputed."

Notes:
- Each item should include `article_number`.

---

## 13) Create Order (Minimal)

User prompt:
"Create a new local delivery order for Ana Ruiz at this address ..."

AI behavior:
- If address is plain text, call `geocode_address` first.
- Call `create_order(...)` with normalized address payload.
- Return compact order summary.

Typical final answer:
"Created order id=1294 (ref: WEB-1294), state Draft, objective local_delivery, operation dropoff."

Notes:
- New orders start in Draft.

---

## 14) Evaluate If Order Fits Existing Route

User prompt:
"Can order 1294 fit route solution 888 without major detour?"

AI behavior:
- Call `evaluate_order_route_fit(route_solution_id=888, order_id=1294)`.
- Explain corridor fit and estimated detour.

Typical final answer:
"Order 1294 fits within the current route corridor. Estimated detour is about 4.2 minutes with best insertion at stop index 6."

Notes:
- Requires order coordinates; geocode first if missing.

---

## Common Clarifications the AI Should Ask

Use a clarification question instead of guessing when:
- The user requests a mutation but does not provide IDs (order/plan/route_group/zone).
- A state name is invalid or ambiguous.
- Address text is provided without enough detail for geocoding.
- A request implies cross-entity action but target scope is unclear.

Typical clarification:
"I can do that. Which plan_id should I use for the reassignment?"

---

## Out of Scope (Current Phase)

These are intentionally deferred and should not be claimed as implemented:
- `update_order_tool`
- `optimize_plan_tool`
- plan execution handlers for local_delivery/international_shipping/store_pickup

If asked for deferred functionality, answer explicitly and offer the closest supported alternative.

Example:
"Full order patch updates are not implemented yet. I can still create orders, change state, assign plans/groups, and add items."

---

## Maintenance Note

When new tools are added to `tool_registry.py`, update this file in the same change set with:
- at least one realistic prompt example per new tool
- expected answer style
- any new prerequisites or safety constraints
