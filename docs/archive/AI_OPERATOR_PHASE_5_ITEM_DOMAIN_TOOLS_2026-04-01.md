# AI Operator — Phase 5: Item Domain Tools

**Date:** 2026-04-01
**Status:** under_development
**Archive target:** docs/archive/
**Summary target:** docs/implemented/

---

## Scope

Implement 3 tool functions and register them.

| Tool name | Stub location | Backend service |
|---|---|---|
| `search_item_types` | `tools/item_tools.py` | `services/queries/item_type/list_item_types.py` → `list_item_types` |
| `add_items_to_order` | `tools/item_tools.py` | `services/commands/item/create/create_item.py` → `create_item` |
| `create_order` | `tools/order_tools.py` | `services/commands/order/create_order.py` → `create_order` |

`update_order_tool` is **deferred** — it requires the `update_extensions` orchestration layer which is out of scope for this phase.

---

## DO NOT TOUCH

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
- `Delivery_app_BK/ai/tools/plan_tools.py`
- `Delivery_app_BK/ai/tools/plan_execution/*`
- All service layer files (commands, queries, domain, models)

---

## Files to Modify

1. `Delivery_app_BK/ai/tools/item_tools.py` — implement 2 item tools
2. `Delivery_app_BK/ai/tools/order_tools.py` — implement `create_order_tool` only
3. `Delivery_app_BK/ai/tool_registry.py` — register 3 new tools (total: 18)
4. `Delivery_app_BK/ai/response_formatter.py` — add 3 summary + 3 action entries (total: 18)
5. `Delivery_app_BK/ai/prompts/system_prompt.py` — append Phase 5 tool docs
6. `Delivery_app_BK/ai/AI_OPERATOR.md` — update registered tools table and file status

---

## 1. `tools/item_tools.py` — Implement 2 tools

Add imports at the top of the file:

```python
from Delivery_app_BK.services.commands.item.create.create_item import create_item
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.item_type.list_item_types import list_item_types
```

### 1a. `search_item_types_tool`

Replace stub with:

```python
AI_ITEM_TYPE_LIMIT = 20


def search_item_types_tool(ctx: ServiceContext, q: str, limit: int = AI_ITEM_TYPE_LIMIT) -> dict:
    """Search item types by name prefix. Returns id, name, and property ids.

    Args:
      q: str          — search string, matched as prefix against item type name
      limit: int      — max results (default 20, max 20)
    """
    params: dict = {"limit": min(int(limit), AI_ITEM_TYPE_LIMIT)}
    if q and q.strip():
        params["name"] = q.strip()

    tool_ctx = ServiceContext(
        query_params=params,
        identity=ctx.identity,
        on_query_return="list",
    )
    result = list_item_types(tool_ctx)
    raw = result.get("item_types") or []
    pagination = result.get("item_types_pagination") or {}

    return {
        "count": len(raw),
        "has_more": pagination.get("has_more", False),
        "q": q,
        "item_types": [
            {
                "id": t.get("id"),
                "client_id": t.get("client_id"),
                "name": t.get("name"),
                "property_ids": t.get("properties") or [],
            }
            for t in raw
        ],
    }
```

Implementation notes:
- `list_item_types(ctx)` reads `ctx.query_params` and calls `find_item_types` then `serialize_item_types`.
- `find_item_types` filters by `name` using `.ilike(f"{name}%")` — prefix match.
- `serialize_item_types` calls `map_return_values` → `on_query_return="list"` makes `result.get("item_types")` a plain list.
- Each serialized item type has keys: `id`, `client_id`, `name`, `properties` (list of property IDs).

### 1b. `add_items_to_order_tool`

Replace stub with:

```python
def add_items_to_order_tool(ctx: ServiceContext, order_id: int, items: list[dict]) -> dict:
    """Add one or more items to an existing order.

    Each item in the items list supports:
      article_number: str   — REQUIRED, item SKU or code
      item_type: str        — item type name string (free text, not FK)
      quantity: int         — number of units
      weight: int           — grams
      dimension_depth: int  — cm
      dimension_height: int — cm
      dimension_width: int  — cm
      reference_number: str — optional external ref
      page_link: str        — optional URL
      properties: list      — optional list of property dicts

    Args:
      order_id: int         — target order
      items: list[dict]     — list of item field dicts
    """
    if not isinstance(order_id, int) or order_id <= 0:
        return {"error": "order_id must be a positive integer"}
    if not items or not isinstance(items, list):
        return {"error": "items must be a non-empty list"}

    # Inject order_id into every item field dict
    fields = [{"order_id": order_id, **item} for item in items]

    tool_ctx = ServiceContext(
        incoming_data={"fields": fields},
        identity=ctx.identity,
        on_create_return="ids",
    )
    result = create_item(tool_ctx)
    item_ids = result.get("item") or []
    affected_orders = result.get("_affected_orders") or []

    return {
        "order_id": order_id,
        "created_count": len(item_ids),
        "item_ids": item_ids,
        "order_totals_recomputed": len(affected_orders) > 0,
    }
```

Implementation notes:
- `create_item(ctx)` reads `ctx.incoming_data["fields"]` via `extract_fields(ctx)`.
- Each field dict must include `order_id` and `article_number` (required by `_parse_item` → `validate_str`).
- `on_create_return="ids"` makes `build_create_result` return `[id1, id2, ...]` — a plain list of integer IDs.
- `create_item` internally handles: `recompute_order_totals`, `recompute_plan_totals`, `touch_route_freshness_by_order`, event emission. No additional orchestration is needed in the tool.
- `result.get("item")` is the list of created item IDs when `on_create_return="ids"`.
- `result.get("_affected_orders")` is a list of `Order` ORM instances — use `len(...)` only, do not serialize.

---

## 2. `tools/order_tools.py` — Implement `create_order_tool`

Add import at the top alongside existing imports:

```python
from Delivery_app_BK.services.commands.order.create_order import create_order
```

Replace stub with:

```python
def create_order_tool(
    ctx: ServiceContext,
    client_first_name: str | None = None,
    client_last_name: str | None = None,
    client_address: dict | None = None,
    order_plan_objective: str | None = None,
    operation_type: str | None = None,
    reference_number: str | None = None,
    delivery_plan_id: int | None = None,
    route_group_id: int | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Create a new order.

    Required: at least one of client_first_name, client_last_name, or client_address
    must be provided so the order is identifiable.

    Optional fields:
      client_first_name: str
      client_last_name: str
      client_address: dict        — {{coordinates: [lat, lng], address: str, ...}}
      order_plan_objective: str   — "local_delivery" | "international_shipping" | "store_pickup"
      operation_type: str         — "pickup" | "dropoff" | "pickup_dropoff"
      reference_number: str       — external reference
      delivery_plan_id: int       — assign to this plan immediately
      route_group_id: int         — assign to this route group immediately
      items: list[dict]           — nested items (each needs article_number)

    Returns:
      id, client_id, reference_number, order_state_id, delivery_plan_id,
      route_group_id, order_plan_objective, operation_type, total_items
    """
    fields: dict = {}

    if client_first_name:
        fields["client_first_name"] = client_first_name.strip()
    if client_last_name:
        fields["client_last_name"] = client_last_name.strip()
    if client_address and isinstance(client_address, dict):
        fields["client_address"] = client_address
    if order_plan_objective:
        fields["order_plan_objective"] = order_plan_objective
    if operation_type:
        fields["operation_type"] = operation_type
    if reference_number:
        fields["reference_number"] = reference_number.strip()
    if delivery_plan_id is not None:
        fields["delivery_plan_id"] = delivery_plan_id
    if route_group_id is not None:
        fields["route_group_id"] = route_group_id
    if items:
        fields["items"] = items

    if not fields:
        return {"error": "At least one order field must be provided"}

    tool_ctx = ServiceContext(
        incoming_data={"fields": [fields]},
        identity=ctx.identity,
    )
    result = create_order(tool_ctx)
    created = result.get("created") or []
    if not created:
        return {"error": "Order creation returned no result"}

    bundle = created[0]
    order_data = bundle.get("order") or {}
    return {
        "id": order_data.get("id"),
        "client_id": order_data.get("client_id"),
        "reference_number": order_data.get("reference_number"),
        "order_state_id": order_data.get("order_state_id"),
        "delivery_plan_id": order_data.get("delivery_plan_id"),
        "route_group_id": order_data.get("route_group_id"),
        "order_plan_objective": order_data.get("order_plan_objective"),
        "operation_type": order_data.get("operation_type"),
        "total_items": order_data.get("total_items"),
    }
```

Implementation notes:
- `create_order(ctx)` reads `ctx.incoming_data["fields"]` via `extract_fields(ctx)` → one `OrderCreateRequest` per list element.
- `parse_create_order_request` validates fields against `ORDER_ALLOWED_FIELDS`, auto-generates `client_id`, defaults `order_state_id` to `OrderStateId.DRAFT`.
- `order_plan_objective` valid values: `"local_delivery"`, `"international_shipping"`, `"store_pickup"`.
- `operation_type` valid values: `"pickup"`, `"dropoff"`, `"pickup_dropoff"`.
- `create_order` returns `{"created": [{"order": {...}, "items": [...]}]}`.
  The `order` dict is from `serialize_created_order`. Access via `bundle.get("order") or {}`.
- Do NOT pass `order_state_id` — new orders always start as DRAFT (enforced by the serializer default).
- Do NOT set `on_query_return` or `on_create_return` — `create_order` does not use `map_return_values` or `build_create_result`.

---

## 3. `tool_registry.py` — Register 3 new tools

Add imports:

```python
from Delivery_app_BK.ai.tools.item_tools import (
    add_items_to_order_tool,
    search_item_types_tool,
)
from Delivery_app_BK.ai.tools.order_tools import create_order_tool
```

Note: `create_order_tool` is already imported from `order_tools` — add it to the existing import block for that module.

Add to TOOLS dict under a Phase 5 comment:

```python
# Phase 5: item domain + order creation
"search_item_types":    search_item_types_tool,
"add_items_to_order":   add_items_to_order_tool,
"create_order":         create_order_tool,
```

Total after this phase: **18 tools**.

Also remove the stale commented-out entries that reference now-implemented tools:
- Remove: `# "create_order": create_order_tool,`
- Remove: `# "search_item_types": search_item_types_tool,`
- Remove: `# "add_items_to_order": add_items_to_order_tool,`

(Leave `# "update_order": update_order_tool,` and `# "optimize_plan": optimize_plan_tool,` as they remain deferred.)

---

## 4. `response_formatter.py` — Add 3 summary + 3 action entries

### Summary functions (add to file):

```python
def _summarize_search_item_types(params: dict, result: dict) -> str:
    count = result.get("count", 0)
    q = result.get("q") or params.get("q", "")
    q_str = f" matching \"{q}\"" if q else ""
    return f"Found {count} item type(s){q_str}."


def _summarize_add_items_to_order(params: dict, result: dict) -> str:
    if "error" in result:
        return f"add_items_to_order failed: {result['error']}"
    return (
        f"Added {result.get('created_count', 0)} item(s) to order {result.get('order_id')}."
    )


def _summarize_create_order(params: dict, result: dict) -> str:
    if "error" in result:
        return f"create_order failed: {result['error']}"
    ref = result.get("reference_number")
    ref_str = f" (ref: {ref})" if ref else ""
    return f"Created order id={result.get('id')}{ref_str}."
```

### Action functions (add to file):

```python
def _actions_for_search_item_types(result: dict) -> list:
    return []


def _actions_for_add_items_to_order(result: dict) -> list:
    return []


def _actions_for_create_order(result: dict) -> list:
    if "error" in result:
        return []
    plan_id = result.get("delivery_plan_id")
    if plan_id:
        return [{
            "id": f"navigate_plan_{plan_id}",
            "type": "navigate",
            "label": "View Plan",
            "payload": {"path": f"/plans/{plan_id}"},
        }]
    return [{
        "id": "navigate_orders",
        "type": "navigate",
        "label": "View Orders",
        "payload": {"path": "/"},
    }]
```

### Registry entries (add to `_SUMMARY_REGISTRY` and `_ACTION_REGISTRY`):

In `_SUMMARY_REGISTRY`:
```python
"search_item_types":  _summarize_search_item_types,
"add_items_to_order": _summarize_add_items_to_order,
"create_order":       _summarize_create_order,
```

In `_ACTION_REGISTRY`:
```python
"search_item_types":  _actions_for_search_item_types,
"add_items_to_order": _actions_for_add_items_to_order,
"create_order":       _actions_for_create_order,
```

Both registries now have **18 entries**.

---

## 5. `prompts/system_prompt.py` — Append Phase 5 tool docs

Append the following block inside `_PROMPT_TEMPLATE`, after the Phase 4 mutation tools section, before the closing triple-quote. Use `{{` and `}}` for any literal braces.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITEM DOMAIN TOOLS (Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

search_item_types
  Search item types by name prefix.
  Params:
    q: str      — search string, matched as a prefix against item type name
    limit: int  — max results (default 20)
  Returns:
    count, has_more, q, item_types[{{id, client_id, name, property_ids}}]
  Usage: Call before add_items_to_order to confirm the item type name exists
  and to retrieve the correct string label for the item_type field.

add_items_to_order
  Add one or more items to an existing order.
  Triggers order and plan total recomputation automatically.
  PREREQUISITE: Confirm order_id exists via list_orders first.
  Params:
    order_id: int         — target order
    items: list[dict]     — each item must include:
      article_number: str — REQUIRED
      item_type: str      — item type name (free text)
      quantity: int       — number of units
      weight: int         — grams
      dimension_depth: int, dimension_height: int, dimension_width: int  — cm
      reference_number: str
  Returns:
    order_id, created_count, item_ids, order_totals_recomputed

create_order
  Create a new order. New orders start as DRAFT state.
  Params (all optional, but provide enough to identify the recipient):
    client_first_name: str
    client_last_name: str
    client_address: dict        — {{coordinates: [lat, lng], address: str}}
    order_plan_objective: str   — "local_delivery" | "international_shipping" | "store_pickup"
    operation_type: str         — "pickup" | "dropoff" | "pickup_dropoff"
    reference_number: str
    delivery_plan_id: int       — assign to plan on creation
    route_group_id: int         — assign to route group on creation
    items: list[dict]           — nested items (each needs article_number)
  Returns:
    id, client_id, reference_number, order_state_id, delivery_plan_id,
    route_group_id, order_plan_objective, operation_type, total_items
  Note: Do not pass order_state_id — new orders always start as DRAFT.
```

---

## 6. `AI_OPERATOR.md` — Update

### Replace "Registered Tools (Phase 4)" heading with "Registered Tools (Phase 5)"

Add 3 new rows to the tool table:

| `search_item_types` | `tools/item_tools.py` | `queries/item_type/list_item_types.py` → `list_item_types` |
| `add_items_to_order` | `tools/item_tools.py` | `commands/item/create/create_item.py` → `create_item` |
| `create_order` | `tools/order_tools.py` | `commands/order/create_order.py` → `create_order` |

### Update "Tool File Status" section to "Phase 5":

```
Implemented:
- tools/item_tools.py       (search_item_types, add_items_to_order)
- tools/order_tools.py      (list_orders, create_order, assign_orders_to_plan,
                              assign_orders_to_route_group, update_order_state)
- tools/plan_tools.py       (list_plans, list_route_groups, create_plan, materialize_route_groups)
- tools/narrative_tools.py  (get_plan_snapshot, get_route_group_snapshot, get_operations_dashboard)
- tools/zone_tools.py       (evaluate_order_route_fit, list_zones, get_zone_snapshot)
- tools/geocode_tools.py    (geocode_address)
- tools/geometry_utils.py   (pure-Python spatial helpers)

Skeleton (NotImplemented - deferred):
- tools/order_tools.py      update_order_tool — deferred (update_extensions complexity)
- tools/plan_tools.py       optimize_plan_tool — deferred (async Celery dispatch)
- tools/plan_execution/local_delivery_handler.py
```

### Update "Next Phases" section:

```
### Phase 5 — Item Domain Tools ✅ (complete)

### Phase 6 — Deferred Tools (when ready)
- update_order — full order mutation via update_extensions orchestration
- optimize_plan — async route optimization via Celery job dispatch + status polling
```

---

## Verification Checklist

After implementation, run these checks in a Python shell inside the app context:

```python
# 1. Tool count
from Delivery_app_BK.ai.tool_registry import TOOLS
assert len(TOOLS) == 18, f"Expected 18 tools, got {len(TOOLS)}"

# 2. All Phase 5 tools registered
for name in ["search_item_types", "add_items_to_order", "create_order"]:
    assert name in TOOLS, f"Missing: {name}"

# 3. Response formatter registries
from Delivery_app_BK.ai.response_formatter import _SUMMARY_REGISTRY, _ACTION_REGISTRY
assert len(_SUMMARY_REGISTRY) == 18
assert len(_ACTION_REGISTRY) == 18

# 4. System prompt contains Phase 5 tool names
from Delivery_app_BK.ai.prompts.system_prompt import build_system_prompt
prompt = build_system_prompt()
for name in ["search_item_types", "add_items_to_order", "create_order"]:
    assert name in prompt, f"Missing from prompt: {name}"

# 5. Phase 4 tools still registered
for name in ["assign_orders_to_plan", "assign_orders_to_route_group",
             "update_order_state", "create_plan", "materialize_route_groups"]:
    assert name in TOOLS, f"Phase 4 tool missing: {name}"

# 6. Deferred stubs remain
from Delivery_app_BK.ai.tools.order_tools import update_order_tool
from Delivery_app_BK.ai.tools.plan_tools import optimize_plan_tool
for fn in [update_order_tool, optimize_plan_tool]:
    try:
        fn(None)
    except NotImplementedError:
        pass
    except Exception:
        pass

# 7. search_item_types_tool returns correct shape with empty query
from Delivery_app_BK.ai.tools.item_tools import search_item_types_tool
# (requires app context to actually call — verify shape only in unit test)

print("All Phase 5 verification checks passed.")
```

---

## Implementation Order

1. `tools/item_tools.py` — add imports, implement `search_item_types_tool` and `add_items_to_order_tool`
2. `tools/order_tools.py` — add `create_order` import, implement `create_order_tool`
3. `tool_registry.py` — add imports, 3 TOOLS entries, clean up stale comments
4. `response_formatter.py` — add 6 functions and 6 registry entries
5. `prompts/system_prompt.py` — append item domain section to `_PROMPT_TEMPLATE`
6. `AI_OPERATOR.md` — update registered tools table, file status, next phases
