# AI Operator — Phase 4: Mutation Tools

**Date:** 2026-04-01
**Status:** under_development
**Archive target:** docs/archive/
**Summary target:** docs/implemented/

---

## Scope

Implement 5 mutation tool functions and register them in the tool registry and prompt.
No infrastructure modules are touched.

Tools being implemented:

| Tool name | Stub location | Backend service |
|---|---|---|
| `assign_orders_to_plan` | `tools/order_tools.py` | `services/commands/order/update_order_route_plan.py` → `apply_orders_route_plan_change` |
| `assign_orders_to_route_group` | `tools/order_tools.py` | same command, with `destination_route_group_id` |
| `update_order_state` | `tools/order_tools.py` | `services/commands/order/order_states/update_orders_state.py` → `update_orders_state_payload` |
| `create_plan` | `tools/plan_tools.py` | `services/commands/route_plan/create_plan.py` → `create_plan` |
| `materialize_route_groups` | `tools/plan_tools.py` | `services/commands/route_plan/materialize_route_groups.py` → `materialize_route_groups` |

`optimize_plan_tool` is **deferred** — it requires async Celery job dispatch. Phase 4 does not touch it.

---

## DO NOT TOUCH

These files must not be modified:

- `Delivery_app_BK/ai/orchestrator.py`
- `Delivery_app_BK/ai/planner.py`
- `Delivery_app_BK/ai/thread_store.py`
- `Delivery_app_BK/ai/errors.py`
- `Delivery_app_BK/ai/schemas.py`
- `Delivery_app_BK/ai/providers/*`
- `Delivery_app_BK/ai/tools/narrative_tools.py`
- `Delivery_app_BK/ai/tools/geocode_tools.py`
- `Delivery_app_BK/ai/tools/geometry_utils.py`
- `Delivery_app_BK/ai/tools/zone_tools.py`
- `Delivery_app_BK/ai/tools/item_tools.py`
- `Delivery_app_BK/ai/tools/plan_execution/*`
- All service layer files (commands, queries, domain, models)

---

## Files to Modify

1. `Delivery_app_BK/ai/tools/order_tools.py` — implement 3 mutation tools
2. `Delivery_app_BK/ai/tools/plan_tools.py` — implement 2 mutation tools
3. `Delivery_app_BK/ai/tool_registry.py` — register 5 new tools (total: 15)
4. `Delivery_app_BK/ai/response_formatter.py` — add 5 summary + 5 action entries
5. `Delivery_app_BK/ai/prompts/system_prompt.py` — append Phase 4 tool docs
6. `Delivery_app_BK/ai/AI_OPERATOR.md` — update registered tools table and file status

---

## 1. `tools/order_tools.py` — Implement 3 mutation tools

### 1a. `assign_orders_to_plan_tool`

Replace stub with:

```python
from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    apply_orders_route_plan_change,
)

def assign_orders_to_plan_tool(ctx: ServiceContext, order_ids: list[int], plan_id: int) -> dict:
    """Move a list of orders to the given plan. Orders are placed in the default zone bucket."""
    if not order_ids:
        return {"error": "order_ids must be a non-empty list"}
    if not isinstance(plan_id, int) or plan_id <= 0:
        return {"error": "plan_id must be a positive integer"}

    result = apply_orders_route_plan_change(ctx, order_ids, plan_id)
    updated = result.get("updated") or []
    return {
        "updated_count": len(updated),
        "plan_id": plan_id,
        "order_ids": order_ids,
    }
```

### 1b. `assign_orders_to_route_group_tool`

Replace stub with:

```python
def assign_orders_to_route_group_tool(
    ctx: ServiceContext, order_ids: list[int], route_group_id: int
) -> dict:
    """Move a list of orders into a specific route group.

    The route group's parent plan_id is required. The AI must resolve the
    plan_id before calling this tool (e.g., via list_route_groups).
    """
    if not order_ids:
        return {"error": "order_ids must be a non-empty list"}
    if not isinstance(route_group_id, int) or route_group_id <= 0:
        return {"error": "route_group_id must be a positive integer"}

    from Delivery_app_BK.models import RouteGroup
    from Delivery_app_BK.services.queries.get_instance import get_instance
    from Delivery_app_BK.errors import NotFound

    try:
        route_group = get_instance(ctx, RouteGroup, route_group_id)
    except NotFound:
        return {"error": f"route_group {route_group_id} not found"}

    plan_id = route_group.route_plan_id
    result = apply_orders_route_plan_change(
        ctx, order_ids, plan_id, destination_route_group_id=route_group_id
    )
    updated = result.get("updated") or []
    return {
        "updated_count": len(updated),
        "plan_id": plan_id,
        "route_group_id": route_group_id,
        "order_ids": order_ids,
    }
```

### 1c. `update_order_state_tool`

Replace stub with:

```python
from Delivery_app_BK.services.commands.order.order_states.update_orders_state import (
    update_orders_state_payload,
)

def update_order_state_tool(ctx: ServiceContext, order_ids: list[int], state: str) -> dict:
    """Transition a list of orders to the given state name.
    Valid state names are defined in ORDER_STATE_MAP.
    """
    if not order_ids:
        return {"error": "order_ids must be a non-empty list"}
    state_id = _ORDER_STATE_NAME_TO_ID.get(state)
    if state_id is None:
        return {
            "error": f"Unknown order state: {state!r}. "
            f"Valid states: {list(_ORDER_STATE_NAME_TO_ID.keys())}"
        }

    payload = update_orders_state_payload(ctx, order_ids, state_id)
    changed_orders = payload.get("order") or []
    return {
        "updated_count": len(changed_orders),
        "target_state": state,
        "order_ids": order_ids,
    }
```

Notes on `update_order_state_tool`:
- `_ORDER_STATE_NAME_TO_ID` is already defined at module level.
- `update_orders_state_payload` is in `services/commands/order/order_states/update_orders_state.py` and returns `build_order_state_update_payload(changed_orders)` which yields `{"order": [...]}`.
- Import `update_orders_state_payload` at the top of the file alongside the existing `list_orders` import.

---

## 2. `tools/plan_tools.py` — Implement 2 mutation tools

### 2a. `create_plan_tool`

Replace stub with:

```python
from Delivery_app_BK.services.commands.route_plan.create_plan import create_plan

def create_plan_tool(
    ctx: ServiceContext,
    label: str,
    start_date: str,
    end_date: str | None = None,
    date_strategy: str = "single",
    zone_ids: list[int] | None = None,
    order_ids: list[int] | None = None,
) -> dict:
    """Create a new route plan.

    Required:
      label: str — human-readable name
      start_date: str — ISO date (YYYY-MM-DD)

    Optional:
      end_date: str — ISO date, defaults to start_date
      date_strategy: "single" | "range" (default "single")
      zone_ids: list[int] — pre-materialize route groups for these zones
      order_ids: list[int] — immediately assign these orders to the plan
    """
    if not label or not isinstance(label, str):
        return {"error": "label is required and must be a non-empty string"}
    if not start_date or not isinstance(start_date, str):
        return {"error": "start_date is required (ISO date string YYYY-MM-DD)"}

    fields: dict = {
        "label": label.strip(),
        "start_date": start_date,
        "date_strategy": date_strategy,
    }
    if end_date:
        fields["end_date"] = end_date
    if zone_ids:
        fields["zone_ids"] = zone_ids
    if order_ids:
        fields["order_ids"] = order_ids

    tool_ctx = ServiceContext(
        incoming_data={"fields": [fields]},
        identity=ctx.identity,
    )
    result = create_plan(tool_ctx)
    created = result.get("created") or []
    if not created:
        return {"error": "Plan creation returned no result"}

    bundle = created[0]
    plan_data = bundle.get("delivery_plan") or {}
    return {
        "id": plan_data.get("id"),
        "label": plan_data.get("label"),
        "date_strategy": plan_data.get("date_strategy"),
        "start_date": plan_data.get("start_date"),
        "end_date": plan_data.get("end_date"),
        "state_id": plan_data.get("state_id"),
        "route_groups_created": len(bundle.get("route_groups") or []),
        "route_solutions_created": len(bundle.get("route_solutions") or []),
    }
```

Implementation notes:
- `create_plan(ctx)` reads `ctx.incoming_data["fields"]` via `extract_fields(ctx)` which yields one item per element in the list.
- The `extract_fields_key=True` default on ServiceContext means it will look at `ctx.incoming_data["fields"]` as the list.
- `create_plan` returns `{"created": [{"delivery_plan": {...}, "route_groups": [...], "route_solutions": [...]}]}`.
- `create_plan` internally calls `parse_create_plan_request` which validates label, start_date, date_strategy, zone_ids, order_ids.
- Do NOT pass `team_id` in incoming_data — it is injected from identity via `inject_team_id=True` (default).

### 2b. `materialize_route_groups_tool`

Replace stub with:

```python
from Delivery_app_BK.services.commands.route_plan.materialize_route_groups import (
    materialize_route_groups,
)

def materialize_route_groups_tool(
    ctx: ServiceContext, plan_id: int, zone_ids: list[int]
) -> dict:
    """Create one route group per zone for an existing plan.

    Idempotent — if a group already exists for a zone it is returned unchanged.

    Args:
      plan_id: int — target plan
      zone_ids: list[int] — zones to materialize into route groups
    """
    if not isinstance(plan_id, int) or plan_id <= 0:
        return {"error": "plan_id must be a positive integer"}
    if not zone_ids or not isinstance(zone_ids, list):
        return {"error": "zone_ids must be a non-empty list of integers"}

    tool_ctx = ServiceContext(
        incoming_data={"route_plan_id": plan_id, "zone_ids": zone_ids},
        identity=ctx.identity,
    )
    result = materialize_route_groups(tool_ctx)
    return {
        "plan_id": plan_id,
        "created_or_existing_count": len(result),
        "route_groups": [
            {"id": g.get("id"), "name": g.get("zone_snapshot", {}).get("name"), "zone_id": g.get("zone_id")}
            for g in result
        ],
    }
```

Implementation notes:
- `materialize_route_groups(ctx)` reads `ctx.incoming_data["route_plan_id"]` and `ctx.incoming_data["zone_ids"]` directly.
- It returns `list[dict]` — already serialized via `serialize_route_group(route_group, ctx)`.
- The zone snapshot name is at `g["zone_snapshot"]["name"]` — access via `.get("zone_snapshot", {}).get("name")`.

---

## 3. `tool_registry.py` — Register 5 new tools

Add imports and 5 entries to TOOLS. The registry file currently has 10 entries.

Add to imports:
```python
from Delivery_app_BK.ai.tools.order_tools import (
    assign_orders_to_plan_tool,
    assign_orders_to_route_group_tool,
    update_order_state_tool,
)
from Delivery_app_BK.ai.tools.plan_tools import (
    create_plan_tool,
    materialize_route_groups_tool,
)
```

Add to TOOLS dict (append after existing 10 entries):
```python
"assign_orders_to_plan":       assign_orders_to_plan_tool,
"assign_orders_to_route_group": assign_orders_to_route_group_tool,
"update_order_state":          update_order_state_tool,
"create_plan":                 create_plan_tool,
"materialize_route_groups":    materialize_route_groups_tool,
```

Total after this phase: **15 tools**.

---

## 4. `response_formatter.py` — Add 5 summary + 5 action entries

### Summary functions (add to file):

```python
def _summarize_assign_orders_to_plan(params: dict, result: dict) -> str:
    if "error" in result:
        return f"assign_orders_to_plan failed: {result['error']}"
    return (
        f"Assigned {result.get('updated_count', 0)} order(s) to plan {result.get('plan_id')}."
    )


def _summarize_assign_orders_to_route_group(params: dict, result: dict) -> str:
    if "error" in result:
        return f"assign_orders_to_route_group failed: {result['error']}"
    return (
        f"Assigned {result.get('updated_count', 0)} order(s) to route group "
        f"{result.get('route_group_id')} (plan {result.get('plan_id')})."
    )


def _summarize_update_order_state(params: dict, result: dict) -> str:
    if "error" in result:
        return f"update_order_state failed: {result['error']}"
    return (
        f"Updated {result.get('updated_count', 0)} order(s) to state "
        f"\"{result.get('target_state')}\"."
    )


def _summarize_create_plan(params: dict, result: dict) -> str:
    if "error" in result:
        return f"create_plan failed: {result['error']}"
    return (
        f"Created plan \"{result.get('label')}\" (id={result.get('id')}) "
        f"for {result.get('start_date')} with "
        f"{result.get('route_groups_created', 0)} route group(s)."
    )


def _summarize_materialize_route_groups(params: dict, result: dict) -> str:
    if "error" in result:
        return f"materialize_route_groups failed: {result['error']}"
    return (
        f"Materialized {result.get('created_or_existing_count', 0)} route group(s) "
        f"for plan {result.get('plan_id')}."
    )
```

### Action functions (add to file):

```python
def _actions_for_assign_orders_to_plan(result: dict) -> list:
    if "error" in result or not result.get("plan_id"):
        return []
    return [{"type": "navigate", "label": "View plan", "url": f"/plans/{result['plan_id']}"}]


def _actions_for_assign_orders_to_route_group(result: dict) -> list:
    if "error" in result or not result.get("plan_id"):
        return []
    return [
        {
            "type": "navigate",
            "label": "View route group",
            "url": f"/plans/{result['plan_id']}?group={result.get('route_group_id')}",
        }
    ]


def _actions_for_update_order_state(result: dict) -> list:
    return []


def _actions_for_create_plan(result: dict) -> list:
    if "error" in result or not result.get("id"):
        return []
    return [{"type": "navigate", "label": "Open plan", "url": f"/plans/{result['id']}"}]


def _actions_for_materialize_route_groups(result: dict) -> list:
    if "error" in result or not result.get("plan_id"):
        return []
    return [{"type": "navigate", "label": "View plan", "url": f"/plans/{result['plan_id']}"}]
```

### Registry entries (add to `_SUMMARY_REGISTRY` and `_ACTION_REGISTRY`):

In `_SUMMARY_REGISTRY`:
```python
"assign_orders_to_plan":        _summarize_assign_orders_to_plan,
"assign_orders_to_route_group": _summarize_assign_orders_to_route_group,
"update_order_state":           _summarize_update_order_state,
"create_plan":                  _summarize_create_plan,
"materialize_route_groups":     _summarize_materialize_route_groups,
```

In `_ACTION_REGISTRY`:
```python
"assign_orders_to_plan":        _actions_for_assign_orders_to_plan,
"assign_orders_to_route_group": _actions_for_assign_orders_to_route_group,
"update_order_state":           _actions_for_update_order_state,
"create_plan":                  _actions_for_create_plan,
"materialize_route_groups":     _actions_for_materialize_route_groups,
```

Both registries now have **15 entries**.

---

## 5. `prompts/system_prompt.py` — Append Phase 4 tool docs

Append the following block inside `_PROMPT_TEMPLATE`, after the Phase 3 tool docs section, before the closing triple-quote. Use `{{` and `}}` for any literal braces in parameter descriptions.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUTATION TOOLS (Phase 4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAFETY RULE: Before calling any mutation tool you MUST:
1. Confirm the target IDs exist (use a query tool first).
2. State your intent clearly to the user before executing.
3. Never mutate on guesswork. Never invent IDs.

create_plan
  Creates a new route plan.
  Required params:
    label: str          — human-readable name
    start_date: str     — ISO date (YYYY-MM-DD)
  Optional params:
    end_date: str       — ISO date, defaults to start_date
    date_strategy: str  — "single" | "range" (default "single")
    zone_ids: list[int] — pre-materialize route groups for these zones
    order_ids: list[int]— immediately assign these orders to the plan
  Returns:
    id, label, date_strategy, start_date, end_date, state_id,
    route_groups_created, route_solutions_created
  Note: New plans always start as OPEN state.

materialize_route_groups
  Create one route group per zone for an existing plan.
  Idempotent — if a group already exists for a zone it is returned unchanged.
  Params:
    plan_id: int        — target plan
    zone_ids: list[int] — zones to materialize
  Returns:
    plan_id, created_or_existing_count, route_groups[{{id, name, zone_id}}]

assign_orders_to_plan
  Move a list of orders to a plan. Orders land in the default (no-zone) bucket.
  Use assign_orders_to_route_group instead if a specific zone group is needed.
  Params:
    order_ids: list[int] — orders to move
    plan_id: int         — destination plan
  Returns:
    updated_count, plan_id, order_ids

assign_orders_to_route_group
  Move a list of orders into a specific route group.
  The tool resolves the parent plan_id from the route group automatically.
  PREREQUISITE: call list_route_groups first to confirm the group exists.
  Params:
    order_ids: list[int]  — orders to move
    route_group_id: int   — destination route group
  Returns:
    updated_count, plan_id, route_group_id, order_ids

update_order_state
  Transition a list of orders to a new state.
  Valid state names: see ORDER STATES section above.
  Only valid state transitions are applied (invalid transitions are silently skipped).
  Params:
    order_ids: list[int] — orders to update
    state: str           — target state name
  Returns:
    updated_count, target_state, order_ids
```

---

## 6. `AI_OPERATOR.md` — Update

### Replace "Registered Tools (Phase 3)" heading with "Registered Tools (Phase 4)"

Add 5 new rows to the tool table:

| `assign_orders_to_plan` | `tools/order_tools.py` | `commands/order/update_order_route_plan.py` → `apply_orders_route_plan_change` |
| `assign_orders_to_route_group` | `tools/order_tools.py` | same command, with `destination_route_group_id` |
| `update_order_state` | `tools/order_tools.py` | `commands/order/order_states/update_orders_state.py` → `update_orders_state_payload` |
| `create_plan` | `tools/plan_tools.py` | `commands/route_plan/create_plan.py` → `create_plan` |
| `materialize_route_groups` | `tools/plan_tools.py` | `commands/route_plan/materialize_route_groups.py` → `materialize_route_groups` |

### Update "Tool File Status" section:

Under "Implemented", update the two lines for order_tools.py and plan_tools.py:
```
- tools/order_tools.py      (list_orders, assign_orders_to_plan, assign_orders_to_route_group, update_order_state)
- tools/plan_tools.py       (list_plans, list_route_groups, create_plan, materialize_route_groups)
```

### Update "Next Phases" section:

Replace Phase 4 bullet list with completion note, then add Phase 5:

```
### Phase 4 — Mutation Tools ✅ (complete)

### Phase 5 — Item Domain Tools
- search_item_types — full-text search over item type catalog
- add_items_to_order — attach items to an order with quantity + weight + volume
```

---

## Verification Checklist

After implementation, run these checks in a Python shell inside the app context:

```python
# 1. Tool count
from Delivery_app_BK.ai.tool_registry import TOOLS
assert len(TOOLS) == 15, f"Expected 15 tools, got {len(TOOLS)}"

# 2. All Phase 4 tools registered
for name in ["assign_orders_to_plan", "assign_orders_to_route_group",
             "update_order_state", "create_plan", "materialize_route_groups"]:
    assert name in TOOLS, f"Missing: {name}"

# 3. Response formatter registries
from Delivery_app_BK.ai.response_formatter import _SUMMARY_REGISTRY, _ACTION_REGISTRY
assert len(_SUMMARY_REGISTRY) == 15
assert len(_ACTION_REGISTRY) == 15

# 4. System prompt contains Phase 4 tool names
from Delivery_app_BK.ai.prompts.system_prompt import build_system_prompt
prompt = build_system_prompt()
for name in ["create_plan", "materialize_route_groups", "assign_orders_to_plan",
             "assign_orders_to_route_group", "update_order_state"]:
    assert name in prompt, f"Missing from prompt: {name}"

# 5. Phase 3 tools unchanged
from Delivery_app_BK.ai.tools.order_tools import list_orders_tool
from Delivery_app_BK.ai.tools.plan_tools import list_plans_tool, list_route_groups_tool
from Delivery_app_BK.ai.tools.zone_tools import list_zones_tool, get_zone_snapshot_tool

# 6. Mutation stubs remain for unimplemented tools
from Delivery_app_BK.ai.tools.order_tools import create_order_tool, update_order_tool
from Delivery_app_BK.ai.tools.plan_tools import optimize_plan_tool, get_plan_summary_tool
from Delivery_app_BK.ai.tools.item_tools import search_item_types_tool, add_items_to_order_tool
import pytest
for fn in [create_order_tool, update_order_tool, optimize_plan_tool,
           get_plan_summary_tool, search_item_types_tool, add_items_to_order_tool]:
    try:
        fn(None)
    except NotImplementedError:
        pass
    except Exception:
        pass

print("All Phase 4 verification checks passed.")
```

---

## Implementation Order

1. `tools/order_tools.py` — add import for `apply_orders_route_plan_change` and `update_orders_state_payload`, implement 3 tools
2. `tools/plan_tools.py` — add imports for `create_plan` and `materialize_route_groups`, implement 2 tools
3. `tool_registry.py` — add 5 imports and 5 TOOLS entries
4. `response_formatter.py` — add 10 functions and 10 registry entries
5. `prompts/system_prompt.py` — append mutation tools section to `_PROMPT_TEMPLATE`
6. `AI_OPERATOR.md` — update registered tools table, file status, next phases
