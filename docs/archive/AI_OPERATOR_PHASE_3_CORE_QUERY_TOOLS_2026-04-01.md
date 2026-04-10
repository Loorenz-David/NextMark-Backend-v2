# AI Operator — Phase 3: Core Query Tools

**Date:** 2026-04-01
**Status:** Ready for implementation
**Depends on:** Phase 1 (Ground Zero) + Phase 2 (Narrative Snapshot Tools) — both completed
**Scope:** `Back_end/Delivery_app_BK/ai/` + one addition to `services/queries/order/find_orders.py`

---

## Objectives

Implement the five "list/query" tools that let the AI navigate the domain —
finding orders, plans, groups, and zones by filter, before deciding what to
observe or mutate. These tools are the AI's eyes when a user gives partial
context ("show me unscheduled orders for tomorrow", "what plans are open?",
"which zones have unassigned orders?").

Also implement the `get_zone_snapshot_tool` here, because it is the natural
pair to `list_zones_tool` and requires the same zone query infrastructure.

**Tools to implement:**

| Tool | File | Wraps |
|---|---|---|
| `list_orders` | `tools/order_tools.py` | `services/queries/order/list_orders.py` |
| `list_plans` | `tools/plan_tools.py` | `services/queries/route_plan/find_plans.py` + `serialize_plan.py` |
| `list_route_groups` | `tools/plan_tools.py` | `services/queries/route_plan/route_groups/list_route_groups.py` |
| `list_zones` | `tools/zone_tools.py` | `services/queries/zones/find_zones.py` + `ZoneTemplate` query |
| `get_zone_snapshot` | `tools/zone_tools.py` | direct Zone + OrderZoneAssignment + RouteGroup query |

**One service-layer addition (non-breaking):**

| File | Change |
|---|---|
| `services/queries/order/find_orders.py` | Add 3 new filter params: `operation_type`, `order_plan_objective`, `zone_id` |

---

## Files: What to Do With Each

### MODIFY (service layer — additive only)
```
services/queries/order/find_orders.py    ← add 3 filter blocks, no other changes
```

### IMPLEMENT (replace NotImplementedError stubs)
```
ai/tools/order_tools.py     ← implement list_orders_tool
ai/tools/plan_tools.py      ← implement list_plans_tool, list_route_groups_tool
ai/tools/zone_tools.py      ← implement list_zones_tool, get_zone_snapshot_tool
```

### ADD ENTRIES
```
ai/tool_registry.py                 ← register 5 new tools (total: 10)
ai/response_formatter.py            ← add 5 summary + 5 action registry entries
ai/prompts/system_prompt.py         ← add tool documentation for 5 tools
ai/AI_OPERATOR.md                   ← update registered tools table
```

### DO NOT TOUCH
```
ai/orchestrator.py, ai/planner.py, ai/thread_store.py,
ai/errors.py, ai/schemas.py, ai/providers/*,
ai/tools/item_tools.py, ai/tools/plan_execution/*,
ai/tools/geocode_tools.py, ai/tools/geometry_utils.py,
ai/tools/narrative_tools.py         ← Phase 2, leave untouched
services/queries/order/list_orders.py   ← no changes needed
```

---

## 1. `services/queries/order/find_orders.py` — Additive Filter Additions

Add three new filter blocks following the exact same pattern as existing filters.
Insert them after the `order_state_id` block and before the `items` sub-query block.

**Do not change anything else in this file.**

```python
# ── NEW: operation_type filter ──────────────────────────────────────────────
if "operation_type" in params:
    query = query.filter(Order.operation_type == params["operation_type"])

# ── NEW: order_plan_objective filter ────────────────────────────────────────
if "order_plan_objective" in params:
    query = query.filter(Order.order_plan_objective == params["order_plan_objective"])

# ── NEW: zone_id filter (via OrderZoneAssignment join) ───────────────────────
if "zone_id" in params:
    if OrderZoneAssignment not in joined_relations:
        query = query.join(
            OrderZoneAssignment,
            OrderZoneAssignment.order_id == Order.id,
        )
        joined_relations.add(OrderZoneAssignment)
    query = query.filter(
        OrderZoneAssignment.zone_id == int(params["zone_id"]),
        OrderZoneAssignment.is_unassigned.is_(False),
    )
```

Also add `OrderZoneAssignment` to the import line at the top of the file:
```python
from Delivery_app_BK.models import db, Order, Item, RoutePlan, OrderDeliveryWindow, OrderZoneAssignment
```

---

## 2. `ai/tools/order_tools.py` — Implement `list_orders_tool`

Replace the `NotImplementedError` stub only. Leave all other stubs unchanged.

### Design decisions

The tool creates a scoped `ServiceContext` — it does not mutate the incoming `ctx`.
All filters are translated to `query_params` and passed to the existing `list_orders()`
service, which already handles `route_plan_id`, `route_group_id`, pagination, and
delegates the rest to `find_orders()`.

The AI-facing return shape is deliberately compact — integer IDs, state names (not IDs),
and a truncated 25-item default. The full serialized objects from `serialize_orders` are
rich but the LLM does not need all fields.

### State name → ID translation (module-level constant)

```python
from Delivery_app_BK.ai.prompts.system_prompt import ORDER_STATE_MAP

_ORDER_STATE_NAME_TO_ID: dict[str, int] = ORDER_STATE_MAP  # {"Draft": 1, ...}
```

### Tool function

```python
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.order.list_orders import list_orders
from Delivery_app_BK.ai.prompts.system_prompt import ORDER_STATE_MAP

_ORDER_STATE_NAME_TO_ID: dict[str, int] = ORDER_STATE_MAP
_ORDER_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in ORDER_STATE_MAP.items()}

AI_ORDER_LIMIT = 25


def list_orders_tool(
    ctx: ServiceContext,
    plan_id: int | None = None,
    route_group_id: int | None = None,
    zone_id: int | None = None,
    scheduled: bool | None = None,
    state: str | list[str] | None = None,
    operation_type: str | None = None,
    order_plan_objective: str | None = None,
    q: str | None = None,
    limit: int = AI_ORDER_LIMIT,
    sort: str = "date_desc",
) -> dict:
    """
    List orders with optional filters. Returns compact order summaries.
    """
    params: dict = {
        "limit": min(int(limit), AI_ORDER_LIMIT),
        "sort": sort,
    }

    if q:
        params["q"] = q.strip()

    # scheduled / unscheduled
    if scheduled is True:
        params["schedule_order"] = True
    elif scheduled is False:
        params["unschedule_order"] = True

    # state: accept name string(s) → translate to IDs
    if state is not None:
        names = [state] if isinstance(state, str) else list(state)
        ids = []
        unknown = []
        for name in names:
            sid = _ORDER_STATE_NAME_TO_ID.get(name)
            if sid is not None:
                ids.append(sid)
            else:
                unknown.append(name)
        if unknown:
            return {
                "error": f"Unknown order state(s): {unknown}. "
                         f"Valid states: {list(_ORDER_STATE_NAME_TO_ID.keys())}"
            }
        params["order_state_id"] = ids

    if operation_type:
        params["operation_type"] = operation_type

    if order_plan_objective:
        params["order_plan_objective"] = order_plan_objective

    if zone_id is not None:
        params["zone_id"] = zone_id

    # Build a tool-scoped ctx so we don't mutate the original
    tool_ctx = ServiceContext(query_params=params, identity=ctx.identity)

    result = list_orders(
        ctx=tool_ctx,
        route_plan_id=plan_id,
        route_group_id=route_group_id,
    )

    raw_orders = result.get("order") or []
    stats = result.get("order_stats") or {}
    pagination = result.get("order_pagination") or {}

    # Build compact AI-facing order summaries
    orders = []
    for o in raw_orders:
        state_id = o.get("order_state_id")
        orders.append({
            "id": o.get("id"),
            "reference_number": o.get("reference_number"),
            "client_name": " ".join(
                filter(None, [o.get("client_first_name"), o.get("client_last_name")])
            ) or None,
            "state": _ORDER_STATE_ID_TO_NAME.get(state_id, str(state_id)),
            "plan_id": o.get("delivery_plan_id"),
            "route_group_id": o.get("route_group_id"),
            "operation_type": o.get("operation_type"),
            "order_plan_objective": o.get("order_plan_objective"),
            "item_type_counts": o.get("item_type_counts"),
            "total_items": o.get("total_items"),
        })

    # Map stats state IDs to names
    by_state_raw = (stats.get("orders") or {}).get("by_state") or {}
    by_state = {
        _ORDER_STATE_ID_TO_NAME.get(int(k), str(k)): v
        for k, v in by_state_raw.items()
    }

    return {
        "count": len(orders),
        "total": (stats.get("orders") or {}).get("total"),
        "by_state": by_state,
        "has_more": pagination.get("has_more", False),
        "orders": orders,
        "filters_applied": {
            k: v for k, v in {
                "plan_id": plan_id,
                "route_group_id": route_group_id,
                "zone_id": zone_id,
                "scheduled": scheduled,
                "state": state,
                "operation_type": operation_type,
                "order_plan_objective": order_plan_objective,
                "q": q,
            }.items() if v is not None
        },
    }
```

---

## 3. `ai/tools/plan_tools.py` — Implement `list_plans_tool` and `list_route_groups_tool`

Replace both stubs. Leave all other stubs (`create_plan_tool`, `optimize_plan_tool`,
`get_plan_summary_tool`, `get_plan_execution_status_tool`) unchanged.

### Module-level imports needed

```python
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.find_plans import find_plans
from Delivery_app_BK.services.queries.route_plan.serialize_plan import serialize_plans
from Delivery_app_BK.services.queries.route_plan.route_groups.list_route_groups import (
    list_route_groups,
)
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.ai.prompts.system_prompt import PLAN_STATE_MAP

_PLAN_STATE_NAME_TO_ID: dict[str, int] = PLAN_STATE_MAP
_PLAN_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in PLAN_STATE_MAP.items()}

AI_PLAN_LIMIT = 20
```

### `list_plans_tool`

```python
def list_plans_tool(
    ctx: ServiceContext,
    label: str | None = None,
    state: str | None = None,
    covers_date: str | None = None,
    covers_start: str | None = None,
    covers_end: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    min_orders: int | None = None,
    max_orders: int | None = None,
    limit: int = AI_PLAN_LIMIT,
    sort: str = "date_desc",
) -> dict:
    """
    List plans with optional filters. Returns plan summaries with route group counts.
    """
    params: dict = {
        "limit": min(int(limit), AI_PLAN_LIMIT),
        "sort": sort,
    }

    if label:
        params["label"] = label.strip()

    if state is not None:
        sid = _PLAN_STATE_NAME_TO_ID.get(state)
        if sid is None:
            return {
                "error": f"Unknown plan state: {state!r}. "
                         f"Valid states: {list(_PLAN_STATE_NAME_TO_ID.keys())}"
            }
        params["state_id"] = sid

    # covers_date is a convenience: same date for both covers_start and covers_end
    if covers_date:
        params["covers_start"] = covers_date
        params["covers_end"] = covers_date
    else:
        if covers_start:
            params["covers_start"] = covers_start
        if covers_end:
            params["covers_end"] = covers_end

    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if min_orders is not None:
        params["min_orders"] = int(min_orders)
    if max_orders is not None:
        params["max_orders"] = int(max_orders)

    if ctx.team_id:
        params["team_id"] = ctx.team_id

    tool_ctx = ServiceContext(query_params=params, identity=ctx.identity)

    from sqlalchemy.orm import selectinload
    from Delivery_app_BK.models import RoutePlan, RouteGroup

    query = find_plans(params, tool_ctx).options(
        selectinload(RoutePlan.route_groups).selectinload(RouteGroup.state)
    )
    plans = query.limit(AI_PLAN_LIMIT + 1).all()
    has_more = len(plans) > AI_PLAN_LIMIT
    page = plans[:AI_PLAN_LIMIT]

    serialized = serialize_plans(page, tool_ctx, include_route_groups_summary=True)
    if not isinstance(serialized, list):
        serialized = [serialized] if serialized else []

    # Build compact AI-facing plan summaries
    result_plans = []
    for p in serialized:
        state_id = p.get("state_id")
        result_plans.append({
            "id": p.get("id"),
            "label": p.get("label"),
            "state": _PLAN_STATE_ID_TO_NAME.get(state_id, str(state_id)),
            "date_strategy": p.get("date_strategy"),
            "start_date": p.get("start_date"),
            "end_date": p.get("end_date"),
            "total_orders": p.get("total_orders"),
            "total_items": p.get("total_items"),
            "group_count": p.get("route_groups_count"),
            "route_groups": [
                {
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "zone_id": g.get("zone_id"),
                    "total_orders": g.get("total_orders"),
                    "state": _PLAN_STATE_ID_TO_NAME.get(
                        (g.get("state") or {}).get("id"), "Unknown"
                    ),
                }
                for g in (p.get("route_groups") or [])
            ],
        })

    return {
        "count": len(result_plans),
        "has_more": has_more,
        "plans": result_plans,
        "filters_applied": {
            k: v for k, v in {
                "label": label,
                "state": state,
                "covers_date": covers_date,
                "covers_start": covers_start,
                "covers_end": covers_end,
                "min_orders": min_orders,
                "max_orders": max_orders,
            }.items() if v is not None
        },
    }
```

### `list_route_groups_tool`

```python
def list_route_groups_tool(ctx: ServiceContext, plan_id: int) -> dict:
    """
    Returns all route groups for a plan, with zone info and active route summary.
    """
    try:
        result = list_route_groups(plan_id, ctx)
    except NotFound as exc:
        return {"error": str(exc)}

    groups = result.get("route_groups", [])

    return {
        "plan_id": plan_id,
        "count": len(groups),
        "route_groups": [
            {
                "id": g.get("id"),
                "name": (g.get("zone_snapshot") or {}).get("name") or "No Zone",
                "zone_id": g.get("zone_id"),
                "state": (g.get("state") or {}).get("name"),
                "total_orders": g.get("total_orders"),
                "item_type_counts": g.get("item_type_counts"),
                "has_active_route": g.get("active_route_solution") is not None,
                "is_optimized": (g.get("active_route_solution") or {}).get("is_optimized"),
                "stop_count": (g.get("active_route_solution") or {}).get("stop_count"),
            }
            for g in groups
        ],
    }
```

---

## 4. `ai/tools/zone_tools.py` — Implement `list_zones_tool` and `get_zone_snapshot_tool`

Replace both stubs. Keep `evaluate_order_route_fit_tool` unchanged.

### Module-level imports needed

```python
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.find_zones import find_zones
from Delivery_app_BK.models import Zone, ZoneTemplate, OrderZoneAssignment, RouteGroup, db
from Delivery_app_BK.services.queries.zones.serialize_zone_template import serialize_zone_template

AI_ZONE_LIMIT = 50
```

### `list_zones_tool`

The tool lists active zones for the team. It uses `find_zones()` with `is_active=True`
as the default, then enriches each zone with its active template's key constraints.
Geometry is excluded — the LLM has no use for polygon coordinates.

```python
def list_zones_tool(
    ctx: ServiceContext,
    city_key: str | None = None,
    zone_type: str | None = None,
    q: str | None = None,
    limit: int = AI_ZONE_LIMIT,
) -> dict:
    """
    Lists active zones for the team. Returns zone identity, centroid,
    and key template constraints (capacity, operating window, eta tolerance).
    """
    params: dict = {
        "is_active": True,
        "sort": "id_asc",
        "limit": min(int(limit), AI_ZONE_LIMIT),
    }
    if ctx.team_id:
        params["team_id"] = ctx.team_id
    if city_key:
        params["city_key"] = city_key.strip()
    if zone_type:
        params["zone_type"] = zone_type.strip()
    if q:
        params["q"] = q.strip()

    tool_ctx = ServiceContext(query_params=params, identity=ctx.identity)
    query = find_zones(params, tool_ctx)
    zones: list[Zone] = query.limit(AI_ZONE_LIMIT + 1).all()
    has_more = len(zones) > AI_ZONE_LIMIT
    page = zones[:AI_ZONE_LIMIT]

    # Load active templates in one query
    zone_ids = [z.id for z in page]
    templates_by_zone: dict[int, dict] = {}
    if zone_ids:
        active_templates = (
            ZoneTemplate.query.filter(
                ZoneTemplate.team_id == ctx.team_id,
                ZoneTemplate.zone_id.in_(zone_ids),
                ZoneTemplate.is_active.is_(True),
            )
            .order_by(ZoneTemplate.version.desc())
            .all()
        )
        for t in active_templates:
            if t.zone_id not in templates_by_zone:
                templates_by_zone[t.zone_id] = serialize_zone_template(t)

    result_zones = []
    for z in page:
        tmpl = templates_by_zone.get(z.id)
        result_zones.append({
            "id": z.id,
            "name": z.name,
            "city_key": z.city_key,
            "zone_type": z.zone_type,
            "centroid_lat": z.centroid_lat,
            "centroid_lng": z.centroid_lng,
            "template": {
                "max_orders_per_route": (tmpl or {}).get("max_orders_per_route"),
                "max_vehicles": (tmpl or {}).get("max_vehicles"),
                "operating_window_start": (tmpl or {}).get("operating_window_start"),
                "operating_window_end": (tmpl or {}).get("operating_window_end"),
                "eta_tolerance_seconds": (tmpl or {}).get("eta_tolerance_seconds"),
            } if tmpl else None,
        })

    return {
        "count": len(result_zones),
        "has_more": has_more,
        "zones": result_zones,
    }
```

### `get_zone_snapshot_tool`

Provides a strategic view of a single zone — not scoped to one plan, but across
all active assignments. This answers "how is this zone being used right now?"

```python
def get_zone_snapshot_tool(
    ctx: ServiceContext,
    zone_id: int,
    date: str | None = None,
) -> dict:
    """
    Returns a strategic snapshot of a zone:
      - identity and template constraints
      - total orders currently assigned to this zone (via OrderZoneAssignment)
      - active route groups linked to this zone (across plans)
      - capacity utilization vs. template limits
      - NarrativeBlocks
    """
    from Delivery_app_BK.ai.tools.narrative_tools import (
        _plan_state_name,
        _state_counts_to_named,
    )

    # ── Load zone ──────────────────────────────────────────────────────────────
    zone: Zone | None = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id:
        return {"error": f"Zone {zone_id} not found."}

    # ── Load active template ───────────────────────────────────────────────────
    template = ZoneTemplate.query.filter_by(
        team_id=ctx.team_id, zone_id=zone_id, is_active=True
    ).first()
    tmpl_data = serialize_zone_template(template) if template else {}

    max_orders_per_route = tmpl_data.get("max_orders_per_route")
    max_vehicles = tmpl_data.get("max_vehicles")
    op_start = tmpl_data.get("operating_window_start")
    op_end = tmpl_data.get("operating_window_end")
    eta_tolerance_s = tmpl_data.get("eta_tolerance_seconds", 0)

    # ── Count assigned orders ─────────────────────────────────────────────────
    # Total non-archived orders assigned to this zone (not is_unassigned)
    assigned_order_count: int = (
        db.session.query(db.func.count(OrderZoneAssignment.id))
        .filter(
            OrderZoneAssignment.team_id == ctx.team_id,
            OrderZoneAssignment.zone_id == zone_id,
            OrderZoneAssignment.is_unassigned.is_(False),
        )
        .scalar()
    ) or 0

    # ── Count unassigned orders for this zone's city ──────────────────────────
    unassigned_count: int = (
        db.session.query(db.func.count(OrderZoneAssignment.id))
        .filter(
            OrderZoneAssignment.team_id == ctx.team_id,
            OrderZoneAssignment.city_key == zone.city_key,
            OrderZoneAssignment.is_unassigned.is_(True),
        )
        .scalar()
    ) or 0

    # ── Load active route groups for this zone ─────────────────────────────────
    route_groups: list[RouteGroup] = (
        RouteGroup.query.filter_by(team_id=ctx.team_id, zone_id=zone_id).all()
    )
    group_summaries = [
        {
            "id": g.id,
            "route_plan_id": g.route_plan_id,
            "state": _plan_state_name(g.state_id),
            "total_orders": g.total_orders or 0,
        }
        for g in route_groups
    ]

    # ── Capacity utilization ──────────────────────────────────────────────────
    # Theoretical max = max_orders_per_route * max_vehicles
    max_capacity = None
    utilization_pct = None
    if max_orders_per_route and max_vehicles:
        max_capacity = max_orders_per_route * max_vehicles
        utilization_pct = round(assigned_order_count / max_capacity * 100, 1) if max_capacity else None

    # ── Build NarrativeBlocks ─────────────────────────────────────────────────
    blocks = []

    blocks.append({
        "type": "stat_kpi",
        "label": "Zone",
        "value": zone.name,
        "meta": {
            "city_key": zone.city_key,
            "zone_type": zone.zone_type,
        },
    })

    blocks.append({
        "type": "stat_kpi",
        "label": "Assigned Orders",
        "value": assigned_order_count,
        "meta": {"unit": "orders"},
    })

    if max_capacity is not None:
        blocks.append({
            "type": "stat_kpi",
            "label": "Capacity",
            "value": f"{assigned_order_count} / {max_capacity}",
            "meta": {
                "utilization_pct": utilization_pct,
                "max_orders_per_route": max_orders_per_route,
                "max_vehicles": max_vehicles,
                "unit": "orders",
            },
        })

    if op_start and op_end:
        blocks.append({
            "type": "stat_kpi",
            "label": "Operating Window",
            "value": f"{op_start} – {op_end}",
            "meta": {"eta_tolerance_seconds": eta_tolerance_s},
        })

    if group_summaries:
        blocks.append({
            "type": "stat_breakdown",
            "label": f"Route Groups ({len(group_summaries)})",
            "value": group_summaries,
            "meta": {"format": "group_list"},
        })

    # Capacity insight / warning
    if utilization_pct is not None:
        if utilization_pct >= 90:
            blocks.append({
                "type": "warning",
                "label": "Near Capacity",
                "value": f"Zone '{zone.name}' is at {utilization_pct}% capacity ({assigned_order_count}/{max_capacity} orders).",
                "meta": {"severity": "high", "color_hint": "red"},
            })
        elif utilization_pct >= 70:
            blocks.append({
                "type": "insight",
                "label": "Utilization",
                "value": f"Zone '{zone.name}' is at {utilization_pct}% capacity.",
                "meta": {"color_hint": "yellow"},
            })
        else:
            blocks.append({
                "type": "insight",
                "label": "Utilization",
                "value": f"Zone '{zone.name}' is at {utilization_pct}% capacity. Room available.",
                "meta": {"color_hint": "green"},
            })

    if unassigned_count > 0:
        blocks.append({
            "type": "warning",
            "label": "Unassigned in City",
            "value": f"{unassigned_count} order(s) in '{zone.city_key}' could not be assigned to any zone.",
            "meta": {"severity": "medium"},
        })

    if not template:
        blocks.append({
            "type": "warning",
            "label": "No Template",
            "value": f"Zone '{zone.name}' has no active template. Capacity limits are unknown.",
            "meta": {"severity": "low"},
        })

    return {
        "zone_id": zone_id,
        "zone_name": zone.name,
        "city_key": zone.city_key,
        "zone_type": zone.zone_type,
        "assigned_order_count": assigned_order_count,
        "max_capacity": max_capacity,
        "utilization_pct": utilization_pct,
        "route_group_count": len(group_summaries),
        "has_template": template is not None,
        "blocks": blocks,
    }
```

---

## 5. `ai/tool_registry.py` — Register 5 New Tools

Add to the existing TOOLS dict. Final count: 10 tools.

```python
from Delivery_app_BK.ai.tools.order_tools import list_orders_tool
from Delivery_app_BK.ai.tools.plan_tools import (
    list_plans_tool,
    list_route_groups_tool,
)
from Delivery_app_BK.ai.tools.zone_tools import (
    list_zones_tool,
    get_zone_snapshot_tool,
    evaluate_order_route_fit_tool,
)
# ... existing imports for Phase 2 tools ...

TOOLS: dict[str, object] = {
    # ── Phase 2: Observation / narrative ─────────────────────────────────────
    "get_plan_snapshot":         get_plan_snapshot_tool,
    "get_route_group_snapshot":  get_route_group_snapshot_tool,
    "get_operations_dashboard":  get_operations_dashboard_tool,
    "evaluate_order_route_fit":  evaluate_order_route_fit_tool,
    "geocode_address":           geocode_address_tool,

    # ── Phase 3: Core query tools ─────────────────────────────────────────────
    "list_orders":               list_orders_tool,
    "list_plans":                list_plans_tool,
    "list_route_groups":         list_route_groups_tool,
    "list_zones":                list_zones_tool,
    "get_zone_snapshot":         get_zone_snapshot_tool,
}
```

---

## 6. `ai/response_formatter.py` — Add 5 Summary + 5 Action Functions

Append these functions and register them. Do not modify existing entries.

### Summary functions

```python
def _summarize_list_orders(params: dict, result: dict) -> str:
    count = result.get("count", 0)
    total = result.get("total")
    filters = result.get("filters_applied") or {}
    context = []
    if filters.get("plan_id"):
        context.append(f"plan #{filters['plan_id']}")
    if filters.get("state"):
        context.append(f"state: {filters['state']}")
    if filters.get("scheduled") is False:
        context.append("unscheduled")
    ctx_str = f" ({', '.join(context)})" if context else ""
    total_str = f" of {total}" if total is not None and total != count else ""
    return f"Found {count}{total_str} orders{ctx_str}."


def _summarize_list_plans(params: dict, result: dict) -> str:
    count = result.get("count", 0)
    filters = result.get("filters_applied") or {}
    context = []
    if filters.get("state"):
        context.append(f"state: {filters['state']}")
    if filters.get("covers_date"):
        context.append(f"date: {filters['covers_date']}")
    ctx_str = f" ({', '.join(context)})" if context else ""
    return f"Found {count} plan(s){ctx_str}."


def _summarize_list_route_groups(params: dict, result: dict) -> str:
    count = result.get("count", 0)
    plan_id = result.get("plan_id", params.get("plan_id", "?"))
    return f"Found {count} route group(s) in plan #{plan_id}."


def _summarize_list_zones(params: dict, result: dict) -> str:
    count = result.get("count", 0)
    return f"Found {count} zone(s)."


def _summarize_get_zone_snapshot(params: dict, result: dict) -> str:
    name = result.get("zone_name", f"zone #{params.get('zone_id', '?')}")
    orders = result.get("assigned_order_count", "?")
    util = result.get("utilization_pct")
    util_str = f", {util}% capacity" if util is not None else ""
    return f"Zone '{name}': {orders} assigned orders{util_str}."
```

### Action functions

```python
def _actions_for_list_orders(result: dict) -> list:
    filters = result.get("filters_applied") or {}
    actions = []
    actions.append({
        "id": "navigate_orders",
        "type": "navigate",
        "label": "Open Orders",
        "payload": {"path": "/"},
    })
    # Build apply_order_filters payload from filters that map to frontend filter keys
    filter_payload: dict = {}
    if filters.get("scheduled") is False:
        filter_payload["unschedule_order"] = True
    if filters.get("scheduled") is True:
        filter_payload["schedule_order"] = True
    if filters.get("state"):
        filter_payload["order_state"] = filters["state"]
    if filters.get("plan_id"):
        filter_payload["plan_id"] = filters["plan_id"]
    if filter_payload:
        actions.append({
            "id": "apply_order_filters",
            "type": "apply_order_filters",
            "label": "Apply Filters",
            "payload": {"mode": "replace", "filters": filter_payload},
        })
    return actions


def _actions_for_list_plans(result: dict) -> list:
    return [{
        "id": "navigate_plans",
        "type": "navigate",
        "label": "View Plans",
        "payload": {"path": "/plans"},
    }]


def _actions_for_list_route_groups(result: dict) -> list:
    plan_id = result.get("plan_id")
    if not plan_id:
        return []
    return [{
        "id": f"navigate_plan_{plan_id}",
        "type": "navigate",
        "label": "Open Plan",
        "payload": {"path": f"/plans/{plan_id}"},
    }]


def _actions_for_list_zones(result: dict) -> list:
    return []


def _actions_for_get_zone_snapshot(result: dict) -> list:
    return []
```

### Updated registry additions (append to existing registries)

```python
# Add to _SUMMARY_REGISTRY:
"list_orders":       _summarize_list_orders,
"list_plans":        _summarize_list_plans,
"list_route_groups": _summarize_list_route_groups,
"list_zones":        _summarize_list_zones,
"get_zone_snapshot": _summarize_get_zone_snapshot,

# Add to _ACTION_REGISTRY:
"list_orders":       _actions_for_list_orders,
"list_plans":        _actions_for_list_plans,
"list_route_groups": _actions_for_list_route_groups,
"list_zones":        _actions_for_list_zones,
"get_zone_snapshot": _actions_for_get_zone_snapshot,
```

---

## 7. `ai/prompts/system_prompt.py` — Add Tool Documentation

Append the following to the `AVAILABLE TOOLS` section, after the existing Phase 2 tools.

```
── QUERY TOOLS (read-only, return lists and summaries) ─────────────────────

list_orders
  Returns a compact list of orders (max 25). Filters are combined with AND.
  Use before any order mutation (update_state, assign_to_plan) to confirm
  the target set. Also use when the user asks to "show", "find", or "list" orders.

  Parameters:
    plan_id               (integer, optional)   — orders assigned to this plan
    route_group_id        (integer, optional)   — orders in this route group
    zone_id               (integer, optional)   — orders assigned to this zone
    scheduled             (boolean, optional)   — true = has plan, false = unassigned
    state                 (string or list[string], optional)
                                                — filter by order state name(s)
                                                  e.g. "Confirmed" or ["Confirmed","Ready"]
    operation_type        (string, optional)    — "pickup" | "dropoff" | "pickup_dropoff"
    order_plan_objective  (string, optional)    — "local_delivery" | "international_shipping"
                                                  | "store_pickup"
    q                     (string, optional)    — free-text search across all string fields
    limit                 (integer, optional)   — max results, default 25
    sort                  (string, optional)    — "date_desc" (default) | "date_asc"

  Returns:
    count, total, by_state {state_name: count}, has_more, orders[], filters_applied


list_plans
  Returns a compact list of plans with route group summaries (max 20).
  Use when the user asks about plans, or before creating/assigning to verify
  no matching plan already exists.

  Parameters:
    label         (string, optional)    — plan label prefix search
    state         (string, optional)    — filter by plan state name (Open/Ready/Processing/Completed/Fail)
    covers_date   (ISO date, optional)  — plans whose window covers this date (convenience shorthand)
    covers_start  (ISO date, optional)  — plans whose window covers start of this range
    covers_end    (ISO date, optional)  — plans whose window covers end of this range
    start_date    (ISO date, optional)  — plans starting on or after this date
    end_date      (ISO date, optional)  — plans ending on or before this date
    min_orders    (integer, optional)   — plans with at least this many orders
    max_orders    (integer, optional)   — plans with at most this many orders
    limit         (integer, optional)   — max results, default 20

  Returns:
    count, has_more, plans[] (each with id, label, state, date range,
    total_orders, group_count, route_groups[])


list_route_groups
  Returns all route groups for a plan with their zone, order count, and
  optimization status.
  Use when you need to know a specific route_group_id before calling
  get_route_group_snapshot or assign_orders_to_route_group.

  Parameters:
    plan_id  (integer, required)  — the plan to inspect

  Returns:
    plan_id, count, route_groups[] (each with id, name/zone, state,
    total_orders, has_active_route, is_optimized, stop_count)


list_zones
  Returns active zones for the team with key template constraints.
  Use when the user asks about zones, or before get_zone_snapshot if
  you need to find a zone_id by name.

  Parameters:
    city_key   (string, optional)   — filter by city
    zone_type  (string, optional)   — "bootstrap" | "system" | "user"
    q          (string, optional)   — free-text search on name, city_key
    limit      (integer, optional)  — max results, default 50

  Returns:
    count, has_more, zones[] (each with id, name, city_key, zone_type,
    centroid_lat/lng, template {max_orders_per_route, max_vehicles,
    operating_window_start/end, eta_tolerance_seconds})


get_zone_snapshot
  Returns a strategic capacity snapshot of a single zone: total orders
  currently assigned, template constraints, capacity utilization, and
  active route groups linked to this zone across all plans.
  Use when the user asks about zone capacity, zone health, or asks to
  "check zone X".

  Parameters:
    zone_id  (integer, required)   — the zone to inspect
    date     (ISO date, optional)  — not yet used (reserved for future scoping)

  Returns:
    zone_name, city_key, zone_type, assigned_order_count, max_capacity,
    utilization_pct, route_group_count, has_template, blocks[]
```

---

## 8. `ai/AI_OPERATOR.md` — Update

Update the **Registered Tools** table to include the 5 new tools.
Update the **Tool File Status** section to show `order_tools.py` and `plan_tools.py`
as partially implemented (list tools done, mutation stubs remain).

---

## Verification Checklist

- [ ] `from Delivery_app_BK.services.queries.order.find_orders import find_orders` — still importable
- [ ] `find_orders` has `operation_type`, `order_plan_objective`, `zone_id` blocks (grep in the file)
- [ ] `OrderZoneAssignment` import added to `find_orders.py`
- [ ] `from Delivery_app_BK.ai.tool_registry import TOOLS` — has exactly 10 keys
- [ ] TOOLS keys include: `list_orders`, `list_plans`, `list_route_groups`, `list_zones`, `get_zone_snapshot`
- [ ] `_SUMMARY_REGISTRY` has 10 entries
- [ ] `_ACTION_REGISTRY` has 10 entries
- [ ] `build_system_prompt()` contains: `"list_orders"`, `"list_plans"`, `"list_route_groups"`, `"list_zones"`, `"get_zone_snapshot"`
- [ ] `list_orders_tool(ctx, state="InvalidState")` returns `{"error": "..."}`, not an exception
- [ ] `list_plans_tool(ctx, state="InvalidState")` returns `{"error": "..."}`, not an exception
- [ ] `list_route_groups_tool(ctx, plan_id=0)` returns `{"error": "..."}` for unknown plan
- [ ] `get_zone_snapshot_tool(ctx, zone_id=0)` returns `{"error": "..."}` for unknown zone
- [ ] `list_zones_tool(ctx)` returns a dict with `"zones"` key (list)
- [ ] `list_orders_tool` still raises `NotImplementedError` — FALSE, it is now implemented
- [ ] `create_plan_tool`, `optimize_plan_tool`, `get_plan_summary_tool`, `get_plan_execution_status_tool` still raise `NotImplementedError`
- [ ] `add_items_to_order_tool`, `search_item_types_tool` still raise `NotImplementedError`
- [ ] Phase 2 tools untouched: `get_plan_snapshot_tool`, `get_route_group_snapshot_tool`, `get_operations_dashboard_tool`, `evaluate_order_route_fit_tool`, `geocode_address_tool` all still importable and callable

---

## What This Phase Does NOT Do

- Does not implement mutation tools (assign, state update, create, optimize) — Phase 4
- Does not implement item tools — Phase 5
- Does not add routes or API endpoints
- Does not touch migrations or models
- The one service change (`find_orders.py`) is additive-only — no existing behavior changes

---

## Next Phase Preview

**Phase 4 — Mutation Tools** will implement:
- `assign_orders_to_plan` — assign order IDs to a plan
- `assign_orders_to_route_group` — assign order IDs to a specific group within a plan
- `update_order_state` — state transition with list_orders prerequisite enforcement
- `create_plan` — create a new RoutePlan
- `materialize_route_groups` — trigger zone-based group creation for a plan
- `optimize_plan` — trigger route optimization for a plan or specific group

**Phase 5 — Item Domain** will implement:
- `search_item_types`, `add_items_to_order`, `create_order`, `update_order`
