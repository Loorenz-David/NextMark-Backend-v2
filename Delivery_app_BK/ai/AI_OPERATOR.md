# AI Logistics Operator — Architecture Reference

> **Maintenance rule:** Update this file after every build, modification, or removal in the `ai/` module.
> This document is the source of truth for understanding, extending, and maintaining the AI operator.

---

## What This Is

The AI Logistics Operator is **not a chatbot**. It is a multi-step tool-calling agent with persistent conversation threads:

```
User input → Thread store (Redis) → Planner (LLM) → selects tool → Backend executes → result back to LLM → repeat → format response → persist
```

The LLM decides *what* to do. The backend decides *how* to do it safely. The AI never touches the database directly.

---

## Module Structure

```
Delivery_app_BK/ai/
  AI_OPERATOR.md          ← this file
  __init__.py

  orchestrator.py         ← entry point: handle_ai_request_with_thread(ctx, user_input, prior_turns, provider, system_prompt)
  planner.py              ← LLM loop: get_next_step(user_input, history, provider, system_prompt)
  thread_store.py         ← Redis CRUD for threads and turns (create, append, list, prune, assert_access)
  response_formatter.py   ← deterministic tool_trace + action generation
  tool_registry.py        ← whitelist: TOOLS dict mapping name → function
  tool_executor.py        ← dispatcher: execute_tool(ctx, tool_name, params)
  schemas.py              ← Pydantic contracts (V2 thread types)
  errors.py               ← ThreadNotFoundError, ThreadAccessError

  prompts/
    system_prompt.py      ← build_system_prompt() → injects state maps from domain enums at request time
                            PLANNER_SYSTEM_PROMPT → module-level constant (fallback/tests)

  providers/
    base.py               ← LLMProvider Protocol: name, complete(system, user) → str
    openai_provider.py    ← ACTIVE: OpenAI gpt-4.1-mini
    anthropic_provider.py ← STUB: raises NotImplementedError
    gemini_provider.py    ← STUB: raises NotImplementedError

  tools/
    plan_tools.py         ← plan-domain tools (list, get, create, optimize, execution status, list routes)
    order_tools.py        ← order-domain tools (list, assign, create, update state, update fields)
    item_tools.py         ← item-domain tools (search types, add items to existing order)
    messaging_tools.py    ← STUB: future messaging tools

    plan_execution/       ← Strategy registry for get_plan_execution_status (one handler per plan type)
      __init__.py         ← get_handler(plan_type) → handler fn
      local_delivery_handler.py        ← IMPLEMENTED: returns is_selected route + stops + driver
      international_shipping_handler.py← STUB: future vendor/carrier API
      store_pickup_handler.py          ← STUB: future pickup slot info
```

---

## Request Flow (V2 — Thread-Based)

```
POST /api_v2/ai/threads                       → create thread, return thread_id
POST /api_v2/ai/threads/<id>/messages         → run planner, persist turns, return structured response
GET  /api_v2/ai/threads/<id>                  → rehydrate thread (user + assistant turns only)
```

### Full message flow:

```
POST /threads/<id>/messages  { message: "...", context: {} }
       ↓
  router: assert_thread_access() → 404/403 if invalid
       ↓
  append user turn to Redis
       ↓
  list_turns(thread_id) → up to MAX_REPLAY_TURNS=20 stored turns
       ↓
  build_system_prompt()  ← injects ORDER_STATE_MAP + PLAN_STATE_MAP from enums (fresh per request)
       ↓
  orchestrator.handle_ai_request_with_thread(ctx, message, prior_turns, system_prompt=prompt)
    → converts stored turns → planner history (user + tool + assistant messages)
    → [loop MAX_STEPS=5]
        planner.get_next_step(user_input, history, provider, system_prompt) → LLM
          → { type: "tool", tool: "...", parameters: {...} }
          OR { type: "final", message: "..." }
        if "tool" → execute_tool(ctx, name, params)
                    → append to local tool_turns list
        if "final" → return OrchestratorResult(final_message, tool_turns, success)
       ↓
  persist each tool turn to Redis
       ↓
  response_formatter.format_response(thread_id, final_message, tool_turns)
    → format_tool_trace() → deterministic AIToolTraceEntry list
    → generate_actions()  → deterministic AIAction list
    → returns AIThreadMessageResponse
       ↓
  persist assistant turn (with tool_trace + actions) to Redis
       ↓
  return { success: true, data: { thread_id, message: { role, content, status_label, tool_trace, actions, data } } }
```

---

## Redis Thread Storage

**Config:**
- `THREAD_TTL = 86400` (24h, sliding — refreshed on every read/write)
- `MAX_STORED_TURNS = 100` (prune oldest when exceeded)
- `MAX_REPLAY_TURNS = 20` (turns fed into planner history per request)

**Redis key pattern** (prefix from `REDIS_KEY_PREFIX` config):
```
{prefix}:ai:thread:{thread_id}:meta         → JSON hash: AIThreadMetadata
{prefix}:ai:thread:{thread_id}:turns        → Redis list: ordered turn IDs
{prefix}:ai:thread:{thread_id}:turn:{id}    → JSON: AIThreadTurn payload
```

**Turn roles:**
- `user` — the user's message
- `tool` — a single tool execution (tool_name, tool_params, tool_result)
- `assistant` — the final LLM response (content, tool_trace, actions)

**Thread ownership:** enforced by `user_id + app_scope` on every request.
`ThreadNotFoundError` → 404. `ThreadAccessError` → 403.

---

## State Maps (injected into prompt at request time)

State names are injected into the system prompt from domain enums — the LLM always uses names, never integers:

```python
# prompts/system_prompt.py
ORDER_STATE_MAP = { "Draft": 1, "Confirmed": 2, "Preparing": 3, "Ready": 4,
                    "Processing": 5, "Completed": 6, "Fail": 7, "Cancelled": 8 }

PLAN_STATE_MAP  = { "Open": 1, "Ready": 2, "Processing": 3, "Completed": 4, "Fail": 5 }
```

Tools that perform state transitions (`update_order_state`) map the name → ID internally and call `update_orders_state()` so all domain events fire correctly.

---

## Registered Tools (current)

| Tool name | File | Domain service |
|---|---|---|
| `list_orders` | `order_tools.py` | `queries/order/list_orders.py` |
| `assign_orders_to_plan` | `order_tools.py` | `commands/order/update_order_delivery_plan.py` |
| `assign_orders` | `order_tools.py` | alias → `assign_orders_to_plan_tool` |
| `update_order_state` | `order_tools.py` | `commands/order/order_states/update_orders_state.py` |
| `update_order` | `order_tools.py` | `commands/order/update_order.py` (MUTABLE_FIELDS allowlist) |
| `create_order` | `order_tools.py` | `commands/order/create_order.py` |
| `list_plans` | `plan_tools.py` | `queries/plan/list_delivery_plans.py` → `find_plans.py` |
| `get_plan_summary` | `plan_tools.py` | `queries/plan/get_plan.py` |
| `create_plan` | `plan_tools.py` | `commands/plan/create_plan.py` |
| `optimize_plan` | `plan_tools.py` | `route_optimization/orchestrator.py` |
| `get_plan_execution_status` | `plan_tools.py` | strategy registry → `plan_execution/` |
| `list_routes` | `plan_tools.py` | direct `RouteSolution` query |
| `search_item_types` | `item_tools.py` | direct `Item` query (deduped by item_type) |
| `add_items_to_order` | `item_tools.py` | `commands/item/create/create_item.py` |

### Order mutation safety rules
- `update_order_state` — AI must always call `list_orders` first. NEVER changes state without confirming targets.
- `update_order` — MUTABLE_FIELDS allowlist enforced in the tool. `order_state_id` and `delivery_plan_id` are forbidden (use dedicated tools).
- `create_order` / `add_items_to_order` — `article_number` is auto-generated (`<item_type_slug>-<6hex>`) if not provided by the user.

---

## Item Creation Pattern

Items have no enforced schema — `item_type` and `properties` are free-form (external sources like Shopify inject their own types). The AI uses a two-step catalog lookup:

```
1. search_item_types(q="table")
   → returns distinct item_types + properties_template from most recent matching items
   → matched=false → proceed with user's label as-is (still valid)

2. create_order(items=[...]) OR add_items_to_order(order_id=N, items=[...])
   → article_number auto-generated if missing: _generate_article_number(item_type) → "table-a3f91c"
```

**Rule:** AI never invents property values. Only sets properties the user explicitly stated.

---

## Plan Execution Status — Strategy Registry

`get_plan_execution_status(plan_id)` dispatches to a plan-type-specific handler via a registry:

```python
# tools/plan_execution/__init__.py
HANDLERS = {
    "local_delivery":         local_delivery_handler.get_execution_status,     # ✅ implemented
    "international_shipping": international_shipping_handler.get_execution_status,  # stub
    "store_pickup":           store_pickup_handler.get_execution_status,        # stub
}
```

**To add a new plan type:** create `tools/plan_execution/<type>_handler.py` implementing `get_execution_status(ctx, plan) -> dict`, add one entry to the registry. The tool, the prompt, and the LLM surface are unchanged.

---

## Response Formatter

`response_formatter.py` converts raw tool turns into frontend-ready structured data. **It never calls the LLM** — all logic is deterministic.

### `format_tool_trace(tool_turns)`
Maps each tool turn → `AIToolTraceEntry`:
- `status`: `"success"` unless result contains `"error"` key
- `summary`: per-tool human string

Current summaries:

| Tool | Summary |
|---|---|
| `list_orders` | "Found N orders." |
| `list_plans` | "Found N plans." |
| `create_plan` | "Created plan {id}." |
| `assign_orders_to_plan` | "Assigned N orders to plan." |
| `optimize_plan` | "Route optimization completed." |
| `get_plan_summary` | "Retrieved plan '{label}'." |
| `update_order_state` | "Updated N orders to '{state}'." |
| `update_order` | "Updated order #{id} ({fields})." |
| `get_plan_execution_status` | "Active route has N stops, driver #X." / "No active route." |
| `list_routes` | "Found N routes." |
| `search_item_types` | "Found N item types in catalog." |
| `add_items_to_order` | "Added N items to order #{id}." |
| `create_order` | "Created order #{id} with N items." |

### `generate_actions(tool_turns)`
Produces `AIAction` list from tool results. Current rules:

| Tool result | Action generated |
|---|---|
| `list_orders` | `navigate` → `/` + `apply_order_filters` with same params |
| `list_plans` | `navigate` → `/plans` |
| `assign_*` | `navigate` → `/plans/<plan_id>` |
| `update_order_state` | `navigate` → `/` (orders list) |
| `create_order` | `navigate` → `/orders/<order_id>` |
| `get_plan_execution_status` / `list_routes` | `navigate` → `/plans/<plan_id>` |

### Action types
`navigate` | `apply_order_filters` | `copy_text` | `open_settings`

---

## Schema Types (V2)

| Type | Purpose |
|---|---|
| `AIThreadMetadata` | thread ownership + timestamps |
| `AIThreadTurn` | a single persisted turn (user/tool/assistant) |
| `AIToolTraceEntry` | one tool execution entry in the response |
| `AIAction` | a frontend-renderable action button |
| `AIThreadCreateResponse` | `POST /threads` response DTO |
| `AIThreadMessageRequest` | `POST /threads/<id>/messages` request DTO |
| `AIThreadMessageResponse` | `POST /threads/<id>/messages` response DTO |
| `AIThreadMessagePayload` | the `message` sub-object in the response |
| `AIThreadGetResponse` | `GET /threads/<id>` response DTO |

---

## Tool Filter Architecture

### `list_orders` → `find_orders.py` (centralized query)

All order queries go through `services/queries/order/find_orders.py`.
Tools inject filters into `ctx.query_params` before calling the service.

| Parameter | Type | Description |
|---|---|---|
| `plan_id` | integer | orders assigned to a specific plan |
| `q` | string | free-text search |
| `s` | list[string] | fields to search: `reference_number`, `order_scalar_id`, `external_source`, `tracking_number`, `client_email`, `client_address`, `client_name`, `client_phone`, `article_number`, `item_type`, `plan_label`, `plan_type` |
| `scheduled` | boolean | `true` = has plan, `false` = unassigned |
| `show_archived` | boolean | archived orders |
| `order_state_id` | int or list[int] | filter by state ID |
| `creation_date_from` | ISO string | created on/after |
| `creation_date_to` | ISO string | created on/before |
| `limit` | integer | max results |
| `sort` | string | `date_asc` or `date_desc` |

### `list_plans` → `find_plans.py` (centralized query)

| Parameter | Type | Description |
|---|---|---|
| `label` | string | plan name prefix |
| `plan_type` | string | `local_delivery` / `international_shipping` / `store_pickup` |
| `plan_state_id` | integer | filter by state ID |
| `covers_start` + `covers_end` | ISO strings | overlap filter: `plan.start_date <= covers_end AND plan.end_date >= covers_start` |
| `start_date` | ISO string | plans starting on/after (browsing) |
| `end_date` | ISO string | plans ending on/before (browsing) |
| `max_orders` / `min_orders` | integer | capacity filters |
| `limit` | integer | max results |

### `list_routes` → direct `RouteSolution` query

| Parameter | Type | Description |
|---|---|---|
| `plan_id` | integer | filter to a specific plan |
| `date` | ISO date | routes whose window covers this date |
| `expected_start_after` | ISO datetime | routes starting at or after |
| `expected_start_before` | ISO datetime | routes starting at or before |
| `driver_id` | integer | filter by driver |
| `is_selected` | boolean | default `true` — active routes only |
| `limit` | integer | default 20 |

---

## Domain Model — Scheduling

```
Order.delivery_plan_id  → NULL = unscheduled, set = scheduled
DeliveryPlan.start_date / end_date → activity window
DeliveryPlan.plan_type  → "local_delivery" | "international_shipping" | "store_pickup"
OrderDeliveryWindow     → time windows (start_at, end_at, window_type) evaluated at optimization
RouteSolution.is_selected = True → the active route for a local_delivery plan
RouteSolutionStop       → one stop per order in the route, with ETA and actual times
```

**"Reschedule" = move an order to a different plan. Never set dates directly on the order.**

Scheduling flow:
1. `list_orders` → get order IDs
2. `list_plans` with `covers_start` + `covers_end` + `plan_type` → find existing plan
3. If found → `assign_orders_to_plan`
4. If not found → `create_plan` → `assign_orders_to_plan`

---

## LLM Provider Pattern

Providers implement the `LLMProvider` Protocol (`providers/base.py`):
```python
class LLMProvider(Protocol):
    name: str
    def complete(self, system: str, user: str) -> str: ...
```

`planner.py` uses `_complete_with_history()` for multi-turn conversations.
OpenAI is called with the full message array directly (native multi-turn).
Other providers fall back to single-turn `complete()` (loses conversation state after step 1).

**To switch provider:** change one line in `orchestrator.py`:
```python
provider = provider or OpenAIProvider()   # swap to AnthropicProvider() or GeminiProvider()
```

---

## Guardrails (non-negotiable)

- **No direct DB access from AI layer.** Tools call domain services only (except `list_routes` and `search_item_types` which do read-only queries directly — safe).
- **Whitelist only.** Only functions in `TOOLS` (tool_registry.py) can be called. Unknown tool names raise `ValueError` — recorded as error turn, loop continues.
- **MAX_STEPS = 5.** Hard cap on tool calls per request. Prevents infinite loops.
- **No dynamic execution.** The LLM returns a tool name string; Python executes a pre-written function.
- **Thread ownership enforced.** Every request checks `user_id + app_scope`.
- **Actions are deterministic.** `response_formatter.py` generates actions from tool results only — never from LLM prose.
- **State transitions go through services.** `update_order_state` calls `update_orders_state()` — events fire correctly.
- **MUTABLE_FIELDS allowlist.** `update_order` rejects `order_state_id` and `delivery_plan_id` at the tool level.

---

## API Contract

### `POST /api_v2/ai/threads`
```json
// Request: {}  (identity from JWT)
// Response:
{ "success": true, "data": { "thread_id": "thr_abc123" } }
```

### `POST /api_v2/ai/threads/<thread_id>/messages`
```json
// Request:
{ "message": "Find unscheduled orders for tomorrow", "context": { "route": "/" } }

// Response:
{
  "success": true,
  "data": {
    "thread_id": "thr_abc123",
    "message": {
      "role": "assistant",
      "content": "Found 12 unscheduled orders.",
      "status_label": "Completed",
      "actions": [
        { "id": "navigate_orders", "type": "navigate", "label": "Open orders", "payload": { "path": "/" } },
        { "type": "apply_order_filters", "label": "Apply filter", "payload": { "mode": "replace", "filters": { "unschedule_order": true } } }
      ],
      "tool_trace": [
        { "id": "tool_1", "tool": "list_orders", "status": "success", "summary": "Found 12 orders.", "params": { "scheduled": false }, "result": { "count": 12 } }
      ],
      "data": null
    }
  }
}
```

### `GET /api_v2/ai/threads/<thread_id>`
```json
{ "success": true, "data": { "thread_id": "thr_abc123", "messages": [ ... ] } }
```

All routes require: `Authorization: Bearer <jwt>` with ADMIN or ASSISTANT role.

### `POST /api_v2/ai/command` — **removed**

---

## Adding a New Tool (checklist)

1. **Write the tool function** in the appropriate `tools/*.py` file:
   - Signature: `def my_tool(ctx: ServiceContext, param1, ...) -> dict`
   - Call only existing domain services — never the DB directly (read-only direct queries are acceptable)
   - Always return a `dict`
2. **Register it** in `tool_registry.py`: add `"my_tool": my_tool_fn` to `TOOLS`
3. **Document it** in `prompts/system_prompt.py` under `AVAILABLE TOOLS`
   - Include all parameters, types, descriptions, and when to use it
4. **Add a `_summarize` branch** in `response_formatter.py` for the tool's trace summary
5. **Add action generation logic** in `generate_actions()` if the tool should produce UI actions
6. **Update this file** — Registered Tools table + any relevant filter tables

## Adding a New Plan Execution Handler (checklist)

1. Create `tools/plan_execution/<type>_handler.py` implementing `get_execution_status(ctx: ServiceContext, plan: DeliveryPlan) -> dict`
2. Add one entry to `HANDLERS` in `tools/plan_execution/__init__.py`
3. Update this file

---

## Removing a Tool (checklist)

1. Remove the entry from `TOOLS` in `tool_registry.py`
2. Remove the function from `tools/*.py`
3. Remove it from `prompts/system_prompt.py`
4. Remove its `_summarize` branch in `response_formatter.py`
5. Update this file

---

## Environment Requirements

```
OPENAI_API_KEY=sk-...   # required in .env and .ebEnv
REDIS_URI=redis://...   # already required for existing Redis features
```
