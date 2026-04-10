# AI Operator Refactor — Phase 1: Ground Zero

**Date:** 2026-04-01
**Status:** Ready for implementation
**Scope:** `Back_end/Delivery_app_BK/ai/`

---

## Context & Motivation

The AI Operator was built around `DeliveryPlan` and a flat order→plan assignment model.
The domain has since changed significantly:

| Old concept | New concept |
|---|---|
| `DeliveryPlan` | `RoutePlan` (aliased, but `RouteGroup` is now the operative unit) |
| Orders belong to a plan | Orders belong to a `RouteGroup` inside a plan |
| No zones | `Zone` → `RouteGroup` → `RouteSolution` (full geographic hierarchy) |
| No operation type | `order.operation_type` (`pickup`, `dropoff`, `pickup_dropoff`) |
| No plan intent on order | `order.order_plan_objective` (`local_delivery`, `international_shipping`, `store_pickup`) |
| Totals computed on demand | Denormalized: Order → RouteGroup → RoutePlan (3-level aggregated JSONB) |
| Narrative stats via `get_analytics_snapshot` (ad-hoc) | Narrative stats as the **primary AI output pattern** |

The old tools called services that no longer match the domain. The old prompt documented a model that no longer exists.

**This phase does NOT implement any new tools.** It clears the old, establishes the correct skeleton and contracts, and updates all architectural documentation. Future phases will implement tools one group at a time.

---

## Objectives

1. Remove all stale tool implementations from `tools/`
2. Clear `tool_registry.py` and `prompts/system_prompt.py` to correct, minimal skeletons
3. Update `response_formatter.py` — remove tool-specific logic, lock in the block architecture for narrative responses
4. Update `schemas.py` — drop V1 compat types, add `NarrativeBlock` to the response contract
5. Create new empty tool files with correct import skeletons: `zone_tools.py`, `narrative_tools.py`
6. Update `AI_OPERATOR.md` to reflect the new domain model
7. Leave `orchestrator.py`, `planner.py`, `thread_store.py`, `tool_executor.py`, `errors.py`, `providers/` **untouched** — they are correct

---

## Files: What to Do With Each

### UNTOUCHED (do not modify)
```
ai/orchestrator.py
ai/planner.py
ai/thread_store.py
ai/errors.py
ai/providers/base.py
ai/providers/openai_provider.py
ai/providers/anthropic_provider.py
ai/providers/gemini_provider.py
```

### RESET (replace with new skeleton — see spec below)
```
ai/tool_registry.py
ai/tool_executor.py          ← minor update only (remove execution_facts injection)
ai/prompts/system_prompt.py
```

### REFACTOR (structural changes — see spec below)
```
ai/schemas.py
ai/response_formatter.py
```

### CLEAR TO SKELETON (empty tool files with correct imports)
```
ai/tools/plan_tools.py
ai/tools/order_tools.py
ai/tools/item_tools.py
ai/tools/plan_execution/__init__.py
ai/tools/plan_execution/local_delivery_handler.py
ai/tools/plan_execution/international_shipping_handler.py
ai/tools/plan_execution/store_pickup_handler.py
```

### CREATE (new empty files)
```
ai/tools/zone_tools.py
ai/tools/narrative_tools.py
```

### UPDATE (architectural documentation)
```
ai/AI_OPERATOR.md
```

---

## Detailed Specs

### 1. `tool_registry.py` — Reset

Replace entirely with:

```python
from __future__ import annotations

# Tool registry — maps tool name → callable.
# Populated as tools are implemented in Phase 2+.
# Import each tool function here and add to TOOLS when ready.

TOOLS: dict[str, object] = {
    # order domain
    # "list_orders":          list_orders_tool,
    # "create_order":         create_order_tool,
    # "update_order":         update_order_tool,
    # "update_order_state":   update_order_state_tool,

    # plan domain
    # "list_plans":           list_plans_tool,
    # "get_plan_summary":     get_plan_summary_tool,
    # "create_plan":          create_plan_tool,
    # "optimize_plan":        optimize_plan_tool,

    # route group domain
    # "list_route_groups":         list_route_groups_tool,
    # "assign_orders_to_group":    assign_orders_to_group_tool,
    # "materialize_route_groups":  materialize_route_groups_tool,

    # zone domain
    # "list_zones":           list_zones_tool,
    # "get_zone_snapshot":    get_zone_snapshot_tool,

    # narrative / stats
    # "get_plan_snapshot":         get_plan_snapshot_tool,
    # "get_operations_dashboard":  get_operations_dashboard_tool,

    # item domain
    # "search_item_types":    search_item_types_tool,
    # "add_items_to_order":   add_items_to_order_tool,
}
```

---

### 2. `tool_executor.py` — Minor Update

Remove the `execution_facts` injection block entirely (lines that injected `facts` into `create_order` params). The new tool functions will handle their own normalization internally.

Keep everything else:
- `execute_tool(ctx, tool_name, params) -> dict` signature
- `ValueError` on unknown tool (recorded as error turn, loop continues)
- Result coercion to dict

The updated `execute_tool` body:

```python
def execute_tool(ctx: ServiceContext, tool_name: str, params: dict) -> dict:
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name!r}")
    fn = TOOLS[tool_name]
    result = fn(ctx, **params)
    if not isinstance(result, dict):
        result = {"result": result}
    return result
```

---

### 3. `schemas.py` — Refactor

**Remove:** All V1 schema types (`AIRequest`, `AIResponse`, `AICommandRequest`, `AICommandResponse`, or any non-V2 types). Remove any forward compat aliases.

**Keep:** All V2 thread types as-is:
- `AIThreadMetadata`
- `AIThreadTurn`
- `AIToolTraceEntry`
- `AIAction`
- `AIThreadCreateResponse`
- `AIThreadMessageRequest`
- `AIThreadMessageResponse`
- `AIThreadMessagePayload`
- `AIThreadGetResponse`

**Add:** A `NarrativeBlock` type to the schema contract. This is the unit of structured output that tools can return and the response formatter will render:

```python
from typing import Literal, Any
from pydantic import BaseModel

class NarrativeBlock(BaseModel):
    """
    A single structured output block returned by a narrative tool.
    The frontend renders each block type differently.
    """
    type: Literal[
        "text",               # plain narrative paragraph
        "stat_kpi",           # single metric with label + value + optional delta
        "stat_trend",         # time-series sparkline values
        "stat_breakdown",     # categorical distribution (e.g. order states by zone)
        "insight",            # synthesized finding — bold callout
        "warning",            # risk or anomaly — flagged visually
        "recommendation",     # suggested action with optional action_id
    ]
    label: str | None = None
    value: Any = None         # str, int, float, list, dict — depends on type
    meta: dict | None = None  # rendering hints (unit, format, color_hint, etc.)
```

Update `AIThreadMessagePayload` to include `blocks: list[NarrativeBlock] | None = None` alongside the existing `data: dict | None`.

```python
class AIThreadMessagePayload(BaseModel):
    role: str
    content: str
    status_label: str
    actions: list[AIAction]
    tool_trace: list[AIToolTraceEntry]
    blocks: list[NarrativeBlock] | None = None   # ← ADD THIS
    data: dict | None = None
```

---

### 4. `response_formatter.py` — Refactor

**Goal:** Remove all tool-specific hardcoded logic. Replace with two clean, extensible registries.

**Remove:**
- All `if tool_name == "list_orders":` / `elif tool_name == "create_plan":` chains in `_summarize()` and `generate_actions()`
- The `get_analytics_snapshot` block-mapping special case

**Replace with two registries (dict-based, at module level):**

```python
# Registry 1: tool name → summary function
# Each function receives tool_params and tool_result, returns a human string.
# Registered during Phase 2+ as tools are implemented.
_SUMMARY_REGISTRY: dict[str, Callable[[dict, dict], str]] = {
    # "list_orders": _summarize_list_orders,
}

# Registry 2: tool name → action generator
# Each function receives tool_result, returns list[AIAction].
# Registered during Phase 2+ as tools are implemented.
_ACTION_REGISTRY: dict[str, Callable[[dict], list[AIAction]]] = {
    # "list_orders": _actions_for_list_orders,
}
```

Update `_summarize(tool_turn)`:
```python
def _summarize(tool_turn: AIThreadTurn) -> str:
    name = tool_turn.tool_name or ""
    fn = _SUMMARY_REGISTRY.get(name)
    if fn:
        return fn(tool_turn.tool_params or {}, tool_turn.tool_result or {})
    return f"Executed {name}."

def generate_actions(tool_turns: list[AIThreadTurn]) -> list[AIAction]:
    actions: list[AIAction] = []
    for turn in tool_turns:
        name = turn.tool_name or ""
        fn = _ACTION_REGISTRY.get(name)
        if fn:
            actions.extend(fn(turn.tool_result or {}))
    return actions
```

**Add:** A `collect_blocks(tool_turns) -> list[NarrativeBlock]` function.
Narrative tools return a `blocks` key in their result dict. This function collects them:

```python
def collect_blocks(tool_turns: list[AIThreadTurn]) -> list[NarrativeBlock]:
    blocks: list[NarrativeBlock] = []
    for turn in tool_turns:
        raw = (turn.tool_result or {}).get("blocks", [])
        for b in raw:
            try:
                blocks.append(NarrativeBlock(**b))
            except Exception:
                pass  # malformed block — skip silently
    return blocks
```

**Update** `format_response()` to call `collect_blocks()` and include blocks in the payload:

```python
def format_response(
    thread_id: str,
    final_message: str,
    tool_turns: list[AIThreadTurn],
) -> AIThreadMessageResponse:
    tool_trace = format_tool_trace(tool_turns)
    actions = generate_actions(tool_turns)
    blocks = collect_blocks(tool_turns)
    payload = AIThreadMessagePayload(
        role="assistant",
        content=final_message,
        status_label="Completed",
        actions=actions,
        tool_trace=tool_trace,
        blocks=blocks if blocks else None,
        data=None,
    )
    return AIThreadMessageResponse(
        success=True,
        data={"thread_id": thread_id, "message": payload},
    )
```

---

### 5. `prompts/system_prompt.py` — Reset

Replace with a **domain-knowledge-only** system prompt. No tool documentation yet — tools are documented here as they are implemented.

The module-level constant `PLANNER_SYSTEM_PROMPT` and the function `build_system_prompt()` must both be preserved (same names, same signature — the orchestrator calls `build_system_prompt()`).

```python
from __future__ import annotations

from Delivery_app_BK.models.tables.route_operations.plan.plan_states import (
    OrderStateEnum,
    PlanStateEnum,
)

# ─────────────────────────────────────────────────────────────────────────────
# Domain state maps (injected into prompt at request time so the LLM always
# uses names, never raw integer IDs).
# ─────────────────────────────────────────────────────────────────────────────

ORDER_STATE_MAP: dict[str, int] = {e.label: e.value for e in OrderStateEnum}
PLAN_STATE_MAP: dict[str, int] = {e.label: e.value for e in PlanStateEnum}


def _build_state_section() -> str:
    order_lines = "\n".join(f"  {k}: {v}" for k, v in ORDER_STATE_MAP.items())
    plan_lines = "\n".join(f"  {k}: {v}" for k, v in PLAN_STATE_MAP.items())
    return f"ORDER STATES:\n{order_lines}\n\nPLAN STATES:\n{plan_lines}"


# ─────────────────────────────────────────────────────────────────────────────
# System prompt template
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """
You are the NextMark AI Logistics Operator — a multi-step tool-calling agent for a
delivery management platform. You are NOT a general-purpose assistant.

Your primary function is to observe, synthesize, and act within the logistics domain:
  - Read operational data across orders, plans, route groups, and zones
  - Communicate findings as structured narrative (blocks of insights, metrics, warnings)
  - Take targeted actions when instructed (create, assign, update, optimize)
  - Never invent data. Never guess IDs. Always verify before mutating.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOMAIN MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROUTE PLAN (RoutePlan)
  - The top-level container for a delivery operation window.
  - Has a date_strategy: "single" (one day) or "range" (multi-day window).
  - Has a state: Open → Ready → Processing → Completed | Fail.
  - Contains one or more RouteGroups.
  - Carries denormalized totals: total_orders, total_item_count,
    total_weight_g, total_volume_cm3, item_type_counts (JSONB).

ROUTE GROUP (RouteGroup)
  - The operative unit inside a plan. Orders live in route groups.
  - Each RouteGroup is linked to a Zone (geographic area) OR is the
    "system default bucket" (is_system_default_bucket=true) for unzoned orders.
  - A RouteGroup may have one or more RouteSolutions (route optimizations).
  - Only one RouteSolution per group is "selected" (is_selected=true) — the active route.
  - Carries denormalized totals: total_orders, order_state_counts,
    total_item_count, item_type_counts.

ORDER (Order)
  - Belongs to a RoutePlan (route_plan_id) and a RouteGroup (route_group_id).
  - order_plan_objective: the intended plan type for this order.
    Values: "local_delivery" | "international_shipping" | "store_pickup"
  - operation_type: the delivery action for this order.
    Values: "pickup" | "dropoff" | "pickup_dropoff"
  - Carries denormalized totals: total_item_count, total_weight_g,
    total_volume_cm3, item_type_counts.
  - States: {order_states}

ZONE (Zone)
  - A geographic polygon (city-level or sub-city).
  - Has a ZoneTemplate with operational defaults:
    max_orders_per_route, max_vehicles, operating_window_start/end,
    eta_tolerance_seconds, preferred_vehicle_ids, default_route_end_strategy.
  - Zones are versioned. Only one active version per team+city.

ORDER ZONE ASSIGNMENT (OrderZoneAssignment)
  - Tracks which Zone an order belongs to.
  - assignment_type: "auto" (polygon match) | "manual" (user override).
  - is_unassigned=true means the order could not be placed in any zone.

ROUTE SOLUTION (RouteSolution)
  - The output of route optimization for a RouteGroup.
  - Contains ordered RouteSolutionStops (one per order).
  - Carries ETA and actual arrival/completion times per stop.

{plan_states}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NARRATIVE OUTPUT PATTERN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When a tool returns structured statistics (a "snapshot"), your final message
should synthesize the data into a narrative — specific, scoped to what the user asked,
and actionable. Do not dump raw numbers. Identify patterns, risks, and what matters most.

Examples of good narrative synthesis:
  "Zone North is at 94% capacity for tomorrow. Two orders have conflicting time windows
   that will likely cause route delays if not resolved before optimization."

  "Plan #12 has 3 route groups: Zone Central (18 orders, ready), Zone South (7 orders,
   unoptimized), and the default bucket (2 unzoned orders). Optimization is recommended
   for Zone South."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAFETY RULES (non-negotiable)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- NEVER change order state without first calling a list/query tool to confirm targets.
- NEVER invent order IDs, plan IDs, zone IDs, or driver IDs.
- NEVER assign an order to a plan type that conflicts with order_plan_objective.
- Use state names (e.g. "Confirmed"), never raw integers.
- If a required parameter is unclear, ask the user — do not guess.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

No tools are currently registered. Tools will be documented here as they are
implemented in subsequent phases.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()


def build_system_prompt() -> str:
    """Build the system prompt, injecting live state maps from domain enums."""
    return _PROMPT_TEMPLATE.format(
        order_states=_build_state_section(),
        plan_states=_build_state_section(),   # shared section covers both
    )


# Fallback constant for tests and provider stubs.
PLANNER_SYSTEM_PROMPT: str = build_system_prompt()
```

> **Note:** The `_PROMPT_TEMPLATE.format()` call uses `{order_states}` and `{plan_states}` as injection points. As new tool groups are implemented in Phase 2+, each tool group adds its documentation block to the `AVAILABLE TOOLS` section. The template is split into a versioned section file at that point.

---

### 6. `tools/plan_tools.py` — Clear to Skeleton

Replace the entire file with:

```python
"""
Plan-domain tools.
Implements: list_plans, get_plan_summary, create_plan, optimize_plan,
            get_plan_execution_status, list_route_groups, materialize_route_groups.

Status: SKELETON — implementations added in Phase 2.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext


# ── list_plans ──────────────────────────────────────────────────────────────
def list_plans_tool(ctx: ServiceContext, **kwargs) -> dict:
    raise NotImplementedError("list_plans_tool — Phase 2")


# ── get_plan_summary ─────────────────────────────────────────────────────────
def get_plan_summary_tool(ctx: ServiceContext, plan_id: int) -> dict:
    raise NotImplementedError("get_plan_summary_tool — Phase 2")


# ── create_plan ──────────────────────────────────────────────────────────────
def create_plan_tool(ctx: ServiceContext, **kwargs) -> dict:
    raise NotImplementedError("create_plan_tool — Phase 2")


# ── optimize_plan ─────────────────────────────────────────────────────────────
def optimize_plan_tool(ctx: ServiceContext, plan_id: int) -> dict:
    raise NotImplementedError("optimize_plan_tool — Phase 2")


# ── get_plan_execution_status ─────────────────────────────────────────────────
def get_plan_execution_status_tool(ctx: ServiceContext, plan_id: int) -> dict:
    raise NotImplementedError("get_plan_execution_status_tool — Phase 2")


# ── list_route_groups ─────────────────────────────────────────────────────────
def list_route_groups_tool(ctx: ServiceContext, plan_id: int, **kwargs) -> dict:
    raise NotImplementedError("list_route_groups_tool — Phase 2")


# ── materialize_route_groups ──────────────────────────────────────────────────
def materialize_route_groups_tool(ctx: ServiceContext, plan_id: int) -> dict:
    raise NotImplementedError("materialize_route_groups_tool — Phase 2")
```

---

### 7. `tools/order_tools.py` — Clear to Skeleton

```python
"""
Order-domain tools.
Implements: list_orders, create_order, update_order, update_order_state,
            assign_orders_to_plan, assign_orders_to_route_group.

Status: SKELETON — implementations added in Phase 2.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext


def list_orders_tool(ctx: ServiceContext, **kwargs) -> dict:
    raise NotImplementedError("list_orders_tool — Phase 2")


def create_order_tool(ctx: ServiceContext, **kwargs) -> dict:
    raise NotImplementedError("create_order_tool — Phase 2")


def update_order_tool(ctx: ServiceContext, order_id: int, **kwargs) -> dict:
    raise NotImplementedError("update_order_tool — Phase 2")


def update_order_state_tool(ctx: ServiceContext, order_ids: list[int], state: str) -> dict:
    raise NotImplementedError("update_order_state_tool — Phase 2")


def assign_orders_to_plan_tool(ctx: ServiceContext, order_ids: list[int], plan_id: int) -> dict:
    raise NotImplementedError("assign_orders_to_plan_tool — Phase 2")


def assign_orders_to_route_group_tool(
    ctx: ServiceContext, order_ids: list[int], route_group_id: int
) -> dict:
    raise NotImplementedError("assign_orders_to_route_group_tool — Phase 2")
```

---

### 8. `tools/item_tools.py` — Clear to Skeleton

```python
"""
Item-domain tools.
Implements: search_item_types, add_items_to_order.

Status: SKELETON — implementations added in Phase 2.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext


def search_item_types_tool(ctx: ServiceContext, q: str) -> dict:
    raise NotImplementedError("search_item_types_tool — Phase 2")


def add_items_to_order_tool(ctx: ServiceContext, order_id: int, items: list[dict]) -> dict:
    raise NotImplementedError("add_items_to_order_tool — Phase 2")
```

---

### 9. `tools/zone_tools.py` — Create New Skeleton

```python
"""
Zone-domain tools.
Implements: list_zones, get_zone_snapshot.

Status: SKELETON — implementations added in Phase 2.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext


def list_zones_tool(ctx: ServiceContext, city_key: str | None = None) -> dict:
    raise NotImplementedError("list_zones_tool — Phase 2")


def get_zone_snapshot_tool(ctx: ServiceContext, zone_id: int, date: str | None = None) -> dict:
    raise NotImplementedError("get_zone_snapshot_tool — Phase 2")
```

---

### 10. `tools/narrative_tools.py` — Create New Skeleton

```python
"""
Narrative / observation tools.
These tools synthesize aggregated data into NarrativeBlock lists.
They do NOT mutate state.

Implements: get_plan_snapshot, get_operations_dashboard, get_route_group_snapshot.

Status: SKELETON — implementations added in Phase 3.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext


def get_plan_snapshot_tool(ctx: ServiceContext, plan_id: int) -> dict:
    """
    Returns a structured snapshot of a plan:
      - plan state, date window, total_orders, item_type_counts
      - per route_group: zone name, order count, state distribution, is_optimized
      - warnings: unzoned orders, time window conflicts, capacity breaches
    Result includes a "blocks" list of NarrativeBlock dicts.
    """
    raise NotImplementedError("get_plan_snapshot_tool — Phase 3")


def get_operations_dashboard_tool(ctx: ServiceContext, date: str | None = None) -> dict:
    """
    Returns a cross-plan view of operations for the given date (defaults to today):
      - active plans with state
      - orders in flight (state breakdown)
      - zone utilization overview
      - alerts: failing orders, overdue routes, driver not yet departed
    Result includes a "blocks" list of NarrativeBlock dicts.
    """
    raise NotImplementedError("get_operations_dashboard_tool — Phase 3")


def get_route_group_snapshot_tool(ctx: ServiceContext, route_group_id: int) -> dict:
    """
    Returns a detailed snapshot of a single route group:
      - zone info and template constraints
      - order list with state, items, timing windows
      - active route: driver, stop sequence, ETA compliance
      - warnings: late stops, unreachable windows, capacity exceeded
    Result includes a "blocks" list of NarrativeBlock dicts.
    """
    raise NotImplementedError("get_route_group_snapshot_tool — Phase 3")
```

---

### 11. `tools/plan_execution/__init__.py` — Clear to Skeleton

```python
"""
Plan execution status — strategy registry.
Dispatches get_plan_execution_status to the correct handler per plan type.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan

from . import local_delivery_handler, international_shipping_handler, store_pickup_handler

HANDLERS: dict[str, object] = {
    "local_delivery":           local_delivery_handler.get_execution_status,
    "international_shipping":   international_shipping_handler.get_execution_status,
    "store_pickup":             store_pickup_handler.get_execution_status,
}


def get_handler(plan_type: str):
    handler = HANDLERS.get(plan_type)
    if handler is None:
        raise ValueError(f"No execution status handler for plan type: {plan_type!r}")
    return handler
```

---

### 12. `tools/plan_execution/local_delivery_handler.py` — Clear to Skeleton

```python
"""
Execution status handler for local_delivery plans.
Returns the selected route, driver, and stop summary for a plan.
Status: SKELETON — Phase 2.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan


def get_execution_status(ctx: ServiceContext, plan: RoutePlan) -> dict:
    raise NotImplementedError("local_delivery get_execution_status — Phase 2")
```

---

### 13. `tools/plan_execution/international_shipping_handler.py` — Clear to Skeleton

```python
"""
Execution status handler for international_shipping plans.
Status: STUB — future vendor/carrier API integration.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan


def get_execution_status(ctx: ServiceContext, plan: RoutePlan) -> dict:
    return {"status": "not_implemented", "plan_type": "international_shipping"}
```

---

### 14. `tools/plan_execution/store_pickup_handler.py` — Clear to Skeleton

```python
"""
Execution status handler for store_pickup plans.
Status: STUB — future pickup slot info integration.
"""
from __future__ import annotations
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan


def get_execution_status(ctx: ServiceContext, plan: RoutePlan) -> dict:
    return {"status": "not_implemented", "plan_type": "store_pickup"}
```

---

### 15. `AI_OPERATOR.md` — Update

Replace the content of `AI_OPERATOR.md` with an updated architecture reference reflecting:
- New domain model (zones, route groups, denormalized totals, order_plan_objective, operation_type)
- Narrative-first output pattern
- Empty tool registry (tools documented here as implemented in Phase 2+)
- NarrativeBlock contract
- Registry-based response_formatter (no hardcoded tool branches)
- Correct file structure (add zone_tools.py, narrative_tools.py)
- Keep all infrastructure sections (orchestrator, planner, thread_store, Redis, providers, request flow) — update only the domain model and tools sections.

The document must still enforce the maintenance rule: **update AI_OPERATOR.md after every build, modification, or removal in the ai/ module.**

---

## Verification Checklist (for Copilot/Codex to confirm after implementation)

- [ ] `from Delivery_app_BK.ai.tool_registry import TOOLS` → `TOOLS` is an empty dict (all entries commented)
- [ ] `from Delivery_app_BK.ai.prompts.system_prompt import build_system_prompt` → callable, returns non-empty string
- [ ] `from Delivery_app_BK.ai.schemas import NarrativeBlock` → importable
- [ ] `AIThreadMessagePayload` has `blocks: list[NarrativeBlock] | None` field
- [ ] `from Delivery_app_BK.ai.response_formatter import collect_blocks` → importable
- [ ] `response_formatter._SUMMARY_REGISTRY` exists as a dict (may be empty)
- [ ] `response_formatter._ACTION_REGISTRY` exists as a dict (may be empty)
- [ ] `from Delivery_app_BK.ai.tools.zone_tools import list_zones_tool` → importable (raises NotImplementedError)
- [ ] `from Delivery_app_BK.ai.tools.narrative_tools import get_plan_snapshot_tool` → importable (raises NotImplementedError)
- [ ] No V1 schema types remain in `schemas.py`
- [ ] No `execution_facts` injection remains in `tool_executor.py`
- [ ] `orchestrator.py`, `planner.py`, `thread_store.py`, `errors.py`, `providers/` are byte-for-byte unchanged
- [ ] `AI_OPERATOR.md` updated: new domain model sections, narrative pattern, correct tool file list, no stale tool docs
- [ ] All Python files in `ai/` are importable without runtime errors (stubs raise NotImplementedError, not ImportError)

---

## What This Phase Does NOT Do

- Does not implement any tool logic
- Does not update the API routers (no route changes)
- Does not add or remove API endpoints
- Does not touch migrations, models, or domain services
- Does not change the OpenAI provider or LLM call logic
- Does not define the tool prompt documentation (that is Phase 2 per tool group)

---

## Next Phase Preview

**Phase 2A — Order & Plan Query Tools** will implement:
- `list_orders_tool` — updated for new order fields (route_group_id, operation_type, order_plan_objective, zone via join)
- `list_plans_tool` — updated for RoutePlan (zone-aware, route_group counts)
- `list_route_groups_tool` — new tool
- Corresponding summary/action registry entries in response_formatter
- Prompt documentation for these tools

**Phase 3 — Narrative Snapshot Tools** will implement:
- `get_plan_snapshot_tool` — full plan health view with NarrativeBlocks
- `get_operations_dashboard_tool` — today's operations summary
- `get_route_group_snapshot_tool` — single group deep-dive
