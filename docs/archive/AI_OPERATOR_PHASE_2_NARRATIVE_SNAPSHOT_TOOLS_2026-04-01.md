# AI Operator — Phase 2: Narrative Snapshot Tools

**Date:** 2026-04-01
**Status:** Ready for implementation
**Depends on:** Phase 1 (Ground Zero) — completed
**Scope:** `Back_end/Delivery_app_BK/ai/`

---

## Objectives

Implement the four read-only observation tools that form the core of the narrative-first
architecture. Each tool reads from the database, synthesizes findings into `NarrativeBlock`
lists, and returns a structured result dict. No mutations in this phase.

Also: register the pre-existing `geocode_address_tool` (found in `ai/tools/geocode_tools.py`,
fully implemented but currently unregistered) — it is a clean, working tool that belongs in
the registry now.

**Tools to implement:**

| Tool | File | Purpose |
|---|---|---|
| `get_plan_snapshot` | `tools/narrative_tools.py` | Health view of a single plan |
| `get_route_group_snapshot` | `tools/narrative_tools.py` | Deep-dive on one route group |
| `get_operations_dashboard` | `tools/narrative_tools.py` | Cross-plan view for a date |
| `evaluate_order_route_fit` | `tools/zone_tools.py` | Route corridor profitability signal |
| `geocode_address` | `tools/geocode_tools.py` | Pre-existing — register only |

**Supporting module to create:**

| File | Purpose |
|---|---|
| `ai/tools/geometry_utils.py` | Pure-Python spatial helpers (radius check, detour estimate) |

---

## Pre-existing asset: `geocode_address_tool`

`Delivery_app_BK/ai/tools/geocode_tools.py` contains a fully implemented
`geocode_address_tool(ctx, q, country_hint)` function. It resolves free-text addresses
via `Delivery_app_BK.geocoding.orchestrator.geocode_address`.

**Do NOT rewrite or modify this file.** Only register it and add its prompt documentation.

---

## Files: What to Do With Each

### CREATE
```
ai/tools/geometry_utils.py          ← new pure-Python geometry helpers
```

### IMPLEMENT (replace NotImplementedError stubs)
```
ai/tools/narrative_tools.py         ← implement 3 snapshot tools
ai/tools/zone_tools.py              ← implement evaluate_order_route_fit
```

### ADD ENTRIES (append to existing registries/sections)
```
ai/tool_registry.py                 ← register 5 tools
ai/response_formatter.py            ← add summary + action registry entries
ai/prompts/system_prompt.py         ← add AVAILABLE TOOLS section
```

### UPDATE (documentation only)
```
ai/AI_OPERATOR.md                   ← update registered tools table
```

### DO NOT TOUCH
```
ai/orchestrator.py, ai/planner.py, ai/thread_store.py,
ai/errors.py, ai/schemas.py, ai/providers/*,
ai/tools/plan_tools.py, ai/tools/order_tools.py, ai/tools/item_tools.py,
ai/tools/plan_execution/*, ai/tools/geocode_tools.py
```

---

## 1. `ai/tools/geometry_utils.py` — Create New

Pure Python. No Flask context. No DB access. No side effects.

```python
"""
geometry_utils.py — pure-Python spatial helpers for route corridor analysis.

All coordinates are (lat, lng) float tuples.
All distances are in meters unless otherwise noted.
"""
from __future__ import annotations
import math


# ── Haversine distance ────────────────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in meters between two WGS-84 points."""
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ── Centroid + radius corridor ────────────────────────────────────────────────

def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return the geographic centroid (mean lat, mean lng) of a point list."""
    if not points:
        raise ValueError("Cannot compute centroid of empty point list.")
    lat = sum(p[0] for p in points) / len(points)
    lng = sum(p[1] for p in points) / len(points)
    return lat, lng


def max_radius_m(center: tuple[float, float], points: list[tuple[float, float]]) -> float:
    """Return the maximum distance from center to any point in the list (meters)."""
    if not points:
        return 0.0
    return max(haversine_m(center[0], center[1], p[0], p[1]) for p in points)


def point_within_corridor(
    candidate: tuple[float, float],
    stop_points: list[tuple[float, float]],
    buffer_m: float,
) -> bool:
    """
    Return True if *candidate* falls within the corridor of *stop_points*.

    Corridor is defined as a circle centred on the centroid of stop_points,
    with radius = max_radius_from_centroid + buffer_m.
    """
    if not stop_points:
        return False
    center = centroid(stop_points)
    route_radius = max_radius_m(center, stop_points)
    distance_to_center = haversine_m(center[0], center[1], candidate[0], candidate[1])
    return distance_to_center <= (route_radius + buffer_m)


# ── Detour estimation ─────────────────────────────────────────────────────────

def cheapest_insertion(
    stop_points: list[tuple[float, float]],
    candidate: tuple[float, float],
) -> dict:
    """
    Find the cheapest insertion position for *candidate* in an ordered stop list.

    Evaluates cost = dist(stop[i], candidate) + dist(candidate, stop[i+1])
                     - dist(stop[i], stop[i+1])
    for every consecutive pair.

    Returns:
        {
            "best_index":           int,    # insert before this stop index
            "detour_meters":        float,  # additional distance added
            "dist_to_prev_m":       float,
            "dist_to_next_m":       float,
        }
    If there is 0 or 1 stop, returns insertion at the end.
    """
    if len(stop_points) == 0:
        return {"best_index": 0, "detour_meters": 0.0, "dist_to_prev_m": 0.0, "dist_to_next_m": 0.0}

    if len(stop_points) == 1:
        d = haversine_m(stop_points[0][0], stop_points[0][1], candidate[0], candidate[1])
        return {"best_index": 1, "detour_meters": d, "dist_to_prev_m": d, "dist_to_next_m": 0.0}

    best_index = 1
    best_cost = float("inf")
    best_to_prev = 0.0
    best_to_next = 0.0

    for i in range(len(stop_points) - 1):
        p0, p1 = stop_points[i], stop_points[i + 1]
        d_prev = haversine_m(p0[0], p0[1], candidate[0], candidate[1])
        d_next = haversine_m(candidate[0], candidate[1], p1[0], p1[1])
        d_orig = haversine_m(p0[0], p0[1], p1[0], p1[1])
        cost = d_prev + d_next - d_orig
        if cost < best_cost:
            best_cost = cost
            best_index = i + 1
            best_to_prev = d_prev
            best_to_next = d_next

    # Also try appending at the end
    last = stop_points[-1]
    d_append = haversine_m(last[0], last[1], candidate[0], candidate[1])
    if d_append < best_cost:
        best_cost = d_append
        best_index = len(stop_points)
        best_to_prev = d_append
        best_to_next = 0.0

    return {
        "best_index": best_index,
        "detour_meters": max(0.0, best_cost),
        "dist_to_prev_m": best_to_prev,
        "dist_to_next_m": best_to_next,
    }


# ── Speed / tolerance conversion ──────────────────────────────────────────────

AVG_CITY_SPEED_MPS = 13.9  # ~50 km/h


def eta_tolerance_to_buffer_m(eta_tolerance_seconds: int) -> float:
    """
    Convert an ETA tolerance (seconds) to a spatial buffer radius (meters).
    Uses AVG_CITY_SPEED_MPS as the conversion factor.
    Minimum buffer is 300 m.
    """
    radius = eta_tolerance_seconds * AVG_CITY_SPEED_MPS
    return max(300.0, radius)


def meters_to_seconds(meters: float, speed_mps: float = AVG_CITY_SPEED_MPS) -> int:
    """Estimate travel time in seconds for a given distance at the given speed."""
    if speed_mps <= 0:
        return 0
    return int(meters / speed_mps)
```

---

## 2. `ai/tools/narrative_tools.py` — Implement

Replace the three `NotImplementedError` stubs with full implementations.

### Shared helpers (module-level, private)

```python
from __future__ import annotations
from datetime import datetime, timezone

from Delivery_app_BK.models import RoutePlan, RouteGroup, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.get_plan import get_plan
from Delivery_app_BK.services.queries.route_plan.route_groups.list_route_groups import (
    list_route_groups,
)
from Delivery_app_BK.services.queries.route_plan.route_groups.get_route_group import (
    get_route_group,
)
from Delivery_app_BK.services.queries.route_plan.find_plans import find_plans
from Delivery_app_BK.services.queries.route_plan.serialize_plan import serialize_plans
from Delivery_app_BK.errors import NotFound

from Delivery_app_BK.ai.prompts.system_prompt import ORDER_STATE_MAP, PLAN_STATE_MAP
```

Build reverse maps at module load time (used to convert integer state IDs to names in
`order_state_counts` JSONB):

```python
# Integer key → state name (handles both str and int JSON keys)
_ORDER_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in ORDER_STATE_MAP.items()}
_PLAN_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in PLAN_STATE_MAP.items()}


def _state_counts_to_named(raw: dict | None) -> dict[str, int]:
    """
    Convert {str(state_id) | int: count} → {state_name: count}.
    Keys that do not map to a known state are kept as-is.
    """
    if not raw:
        return {}
    result = {}
    for k, v in raw.items():
        try:
            state_id = int(k)
        except (ValueError, TypeError):
            result[str(k)] = v
            continue
        name = _ORDER_STATE_ID_TO_NAME.get(state_id, str(state_id))
        result[name] = result.get(name, 0) + v
    return result


def _plan_state_name(state_id: int | None) -> str:
    if state_id is None:
        return "Unknown"
    return _PLAN_STATE_ID_TO_NAME.get(state_id, str(state_id))
```

---

### Tool: `get_plan_snapshot_tool`

```python
def get_plan_snapshot_tool(ctx: ServiceContext, plan_id: int) -> dict:
    """
    Returns a structured snapshot of a plan:
      - plan state, date window, total_orders, item_type_counts
      - per route_group: zone name, order count, state distribution, is_optimized
      - warnings: unzoned orders, unoptimized groups
    Result includes a 'blocks' list of NarrativeBlock dicts.
    """
    try:
        plan_data = get_plan(plan_id, ctx)
    except NotFound as exc:
        return {"error": str(exc)}

    plan = plan_data["route_plan"]

    try:
        groups_data = list_route_groups(plan_id, ctx)
    except NotFound as exc:
        return {"error": str(exc)}

    groups = groups_data.get("route_groups", [])

    # ── Aggregate ──────────────────────────────────────────────────────────────
    total_orders = plan.get("total_orders") or 0
    total_items = plan.get("total_items") or plan.get("total_item_count") or 0
    item_type_counts: dict = plan.get("item_type_counts") or {}
    state_id = plan.get("state_id")
    state_name = _plan_state_name(state_id)
    start_date = plan.get("start_date")
    end_date = plan.get("end_date")
    label = plan.get("label", f"Plan #{plan_id}")

    unoptimized_groups = []
    unzoned_orders = 0
    group_breakdown = []

    for g in groups:
        zone_id = g.get("zone_id")
        gname = (g.get("zone_snapshot") or {}).get("name") or "No Zone"
        g_orders = g.get("total_orders") or 0
        g_state_id = (g.get("state") or {}).get("id")
        g_state = _plan_state_name(g_state_id)
        active_route = g.get("active_route_solution")
        is_optimized = (active_route or {}).get("is_optimized", "not_optimized")

        group_breakdown.append({
            "name": gname,
            "zone_id": zone_id,
            "total_orders": g_orders,
            "state": g_state,
            "is_optimized": is_optimized,
            "has_active_route": active_route is not None,
        })

        if zone_id is None:
            unzoned_orders += g_orders

        if active_route is None or is_optimized == "not_optimized":
            unoptimized_groups.append(gname)

    # ── Build NarrativeBlocks ──────────────────────────────────────────────────
    blocks = []

    # Plan identity
    date_range = f"{start_date or '?'} → {end_date or '?'}"
    blocks.append({
        "type": "stat_kpi",
        "label": "Plan",
        "value": label,
        "meta": {"state": state_name, "date_range": date_range},
    })

    blocks.append({
        "type": "stat_kpi",
        "label": "Total Orders",
        "value": total_orders,
        "meta": {"unit": "orders"},
    })

    if total_items:
        blocks.append({
            "type": "stat_kpi",
            "label": "Total Items",
            "value": total_items,
            "meta": {"unit": "items"},
        })

    if item_type_counts:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Item Types",
            "value": item_type_counts,
            "meta": {"format": "count_map"},
        })

    if group_breakdown:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Orders by Group",
            "value": group_breakdown,
            "meta": {"format": "group_list"},
        })

    # Insight: overall readiness
    optimized_count = sum(1 for g in group_breakdown if g["is_optimized"] != "not_optimized")
    group_count = len(group_breakdown)
    if group_count > 0 and optimized_count == group_count:
        blocks.append({
            "type": "insight",
            "label": "Route Status",
            "value": f"All {group_count} groups are optimized.",
            "meta": {"color_hint": "green"},
        })
    elif group_count > 0:
        blocks.append({
            "type": "insight",
            "label": "Route Status",
            "value": f"{optimized_count} of {group_count} groups are optimized.",
            "meta": {"color_hint": "yellow" if optimized_count > 0 else "orange"},
        })

    # Warnings
    for gname in unoptimized_groups:
        blocks.append({
            "type": "warning",
            "label": "Needs Optimization",
            "value": f"Group '{gname}' has no optimized route.",
            "meta": {"severity": "medium"},
        })

    if unzoned_orders > 0:
        blocks.append({
            "type": "warning",
            "label": "Unzoned Orders",
            "value": f"{unzoned_orders} order(s) are in the default bucket with no zone assignment.",
            "meta": {"severity": "low"},
        })

    return {
        "plan_id": plan_id,
        "plan_label": label,
        "state_id": state_id,
        "state_name": state_name,
        "total_orders": total_orders,
        "group_count": group_count,
        "has_unzoned_orders": unzoned_orders > 0,
        "unoptimized_group_count": len(unoptimized_groups),
        "blocks": blocks,
    }
```

---

### Tool: `get_route_group_snapshot_tool`

```python
def get_route_group_snapshot_tool(ctx: ServiceContext, route_group_id: int) -> dict:
    """
    Returns a detailed snapshot of a single route group:
      - zone info and template constraints
      - order state distribution
      - active route: driver, stop count, distance, travel time
      - warnings: constraint violations, stale ETAs, out-of-range stops
    Result includes a 'blocks' list of NarrativeBlock dicts.
    """
    # Load the route group to get its route_plan_id
    route_group: RouteGroup | None = db.session.get(RouteGroup, route_group_id)
    if route_group is None or route_group.team_id != ctx.team_id:
        return {"error": f"Route group {route_group_id} not found."}

    plan_id = route_group.route_plan_id

    try:
        data = get_route_group(plan_id, route_group_id, ctx)
    except NotFound as exc:
        return {"error": str(exc)}

    rg = data.get("route_group", {})
    route_solutions = data.get("route_solutions", [])
    stops = data.get("route_solution_stops", [])

    selected_solution = next(
        (s for s in route_solutions if s.get("is_selected")),
        route_solutions[0] if route_solutions else None,
    )

    # ── Extract fields ─────────────────────────────────────────────────────────
    zone_snapshot = rg.get("zone_snapshot") or {}
    zone_name = zone_snapshot.get("name") or "No Zone"
    template_snapshot = rg.get("template_snapshot") or {}
    state_id = (rg.get("state") or {}).get("id")
    state_name = _plan_state_name(state_id)
    total_orders = rg.get("total_orders") or 0
    order_state_counts = _state_counts_to_named(rg.get("order_state_counts"))
    item_type_counts = rg.get("item_type_counts") or {}

    # Active route fields
    has_active_route = selected_solution is not None
    driver_id = (selected_solution or {}).get("driver_id")
    driver_name = (selected_solution or {}).get("driver_name")
    is_optimized = (selected_solution or {}).get("is_optimized", "not_optimized")
    total_distance_m = (selected_solution or {}).get("total_distance_meters")
    total_travel_s = (selected_solution or {}).get("total_travel_time_seconds")

    # Stop health
    constraint_violations = [s for s in stops if s.get("has_constraint_violation")]
    out_of_range = [s for s in stops if s.get("in_range") is False]
    stale_eta = [s for s in stops if s.get("eta_status") == "stale"]

    # ── Build NarrativeBlocks ──────────────────────────────────────────────────
    blocks = []

    blocks.append({
        "type": "stat_kpi",
        "label": "Route Group",
        "value": zone_name,
        "meta": {"state": state_name, "route_plan_id": plan_id},
    })

    blocks.append({
        "type": "stat_kpi",
        "label": "Total Orders",
        "value": total_orders,
        "meta": {"unit": "orders"},
    })

    if order_state_counts:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Order States",
            "value": order_state_counts,
            "meta": {"format": "state_count_map"},
        })

    if item_type_counts:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Item Types",
            "value": item_type_counts,
            "meta": {"format": "count_map"},
        })

    # Route status
    if has_active_route:
        distance_km = round(total_distance_m / 1000, 1) if total_distance_m else None
        travel_min = round(total_travel_s / 60) if total_travel_s else None

        blocks.append({
            "type": "insight",
            "label": "Active Route",
            "value": (
                f"{len(stops)} stops, "
                f"{distance_km} km, "
                f"~{travel_min} min. "
                f"Driver: {driver_name or 'unassigned'}."
            ),
            "meta": {
                "is_optimized": is_optimized,
                "driver_id": driver_id,
                "stop_count": len(stops),
            },
        })

        if total_distance_m is not None:
            blocks.append({
                "type": "stat_kpi",
                "label": "Route Distance",
                "value": distance_km,
                "meta": {"unit": "km"},
            })

        if total_travel_s is not None:
            blocks.append({
                "type": "stat_kpi",
                "label": "Est. Travel Time",
                "value": travel_min,
                "meta": {"unit": "min"},
            })
    else:
        blocks.append({
            "type": "insight",
            "label": "Route Status",
            "value": "No route solution exists for this group yet.",
            "meta": {"color_hint": "orange"},
        })

    # Driver
    if has_active_route and not driver_id:
        blocks.append({
            "type": "warning",
            "label": "No Driver",
            "value": "Active route has no driver assigned.",
            "meta": {"severity": "high"},
        })

    # Optimization
    if has_active_route and is_optimized == "not_optimized":
        blocks.append({
            "type": "warning",
            "label": "Not Optimized",
            "value": "Route solution exists but has not been optimized.",
            "meta": {"severity": "medium"},
        })

    # Stop health warnings
    if constraint_violations:
        blocks.append({
            "type": "warning",
            "label": "Constraint Violations",
            "value": f"{len(constraint_violations)} stop(s) have constraint violations.",
            "meta": {
                "severity": "high",
                "stop_ids": [s.get("id") for s in constraint_violations],
            },
        })

    if out_of_range:
        blocks.append({
            "type": "warning",
            "label": "Out of Range",
            "value": f"{len(out_of_range)} stop(s) are marked out of range.",
            "meta": {"severity": "medium"},
        })

    if stale_eta:
        blocks.append({
            "type": "warning",
            "label": "Stale ETAs",
            "value": f"{len(stale_eta)} stop(s) have stale ETA status.",
            "meta": {"severity": "low"},
        })

    return {
        "route_group_id": route_group_id,
        "zone_name": zone_name,
        "route_plan_id": plan_id,
        "state_id": state_id,
        "state_name": state_name,
        "total_orders": total_orders,
        "has_active_route": has_active_route,
        "driver_assigned": bool(driver_id),
        "is_optimized": is_optimized,
        "constraint_violations_count": len(constraint_violations),
        "blocks": blocks,
    }
```

---

### Tool: `get_operations_dashboard_tool`

```python
def get_operations_dashboard_tool(ctx: ServiceContext, date: str | None = None) -> dict:
    """
    Returns a cross-plan view of operations for the given date (defaults to today).
    Includes active plan count, aggregate order state distribution, and alerts.
    Result includes a 'blocks' list of NarrativeBlock dicts.
    """
    from Delivery_app_BK.services.utils import inject_team_id

    if date is None:
        date = datetime.now(timezone.utc).date().isoformat()

    params: dict = {
        "covers_start": date,
        "covers_end": date,
        "limit": 50,
    }
    if ctx.team_id:
        params["team_id"] = ctx.team_id

    query = find_plans(params, ctx)
    plans: list[RoutePlan] = query.all()

    if not plans:
        return {
            "date": date,
            "plan_count": 0,
            "total_orders": 0,
            "blocks": [
                {
                    "type": "insight",
                    "label": "No Active Plans",
                    "value": f"No plans are active on {date}.",
                    "meta": {"color_hint": "grey"},
                }
            ],
        }

    # ── Aggregate across plans ─────────────────────────────────────────────────
    total_orders = 0
    plans_by_state: dict[str, int] = {}
    orders_by_state: dict[str, int] = {}
    alerts = []

    for plan in plans:
        total_orders += plan.total_orders or 0
        state_name = _plan_state_name(plan.state_id)
        plans_by_state[state_name] = plans_by_state.get(state_name, 0) + 1

        # Aggregate order_state_counts from each route group
        for group in (plan.route_groups or []):
            named = _state_counts_to_named(getattr(group, "order_state_counts", None))
            for sname, cnt in named.items():
                orders_by_state[sname] = orders_by_state.get(sname, 0) + cnt

        # Alerts: Open plans with orders
        if plan.state_id == 1 and (plan.total_orders or 0) > 0:  # state 1 = Open
            alerts.append({
                "type": "open_plan_with_orders",
                "message": f"Plan '{plan.label}' is still Open with {plan.total_orders} orders.",
                "plan_id": plan.id,
            })

        # Alerts: Plans with no route groups
        groups = list(plan.route_groups or [])
        if not groups and (plan.total_orders or 0) > 0:
            alerts.append({
                "type": "no_route_groups",
                "message": f"Plan '{plan.label}' has orders but no route groups.",
                "plan_id": plan.id,
            })

    # ── Build NarrativeBlocks ──────────────────────────────────────────────────
    blocks = []

    blocks.append({
        "type": "stat_kpi",
        "label": "Active Plans",
        "value": len(plans),
        "meta": {"date": date, "unit": "plans"},
    })

    blocks.append({
        "type": "stat_kpi",
        "label": "Total Orders",
        "value": total_orders,
        "meta": {"unit": "orders"},
    })

    if plans_by_state:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Plans by State",
            "value": plans_by_state,
            "meta": {"format": "state_count_map"},
        })

    if orders_by_state:
        blocks.append({
            "type": "stat_breakdown",
            "label": "Orders by State",
            "value": orders_by_state,
            "meta": {"format": "state_count_map"},
        })

    # Insight summary
    processing_count = plans_by_state.get("Processing", 0)
    open_count = plans_by_state.get("Open", 0)
    ready_count = plans_by_state.get("Ready", 0)
    parts = []
    if processing_count:
        parts.append(f"{processing_count} processing")
    if ready_count:
        parts.append(f"{ready_count} ready")
    if open_count:
        parts.append(f"{open_count} still open")
    if parts:
        blocks.append({
            "type": "insight",
            "label": "Operations Summary",
            "value": f"{len(plans)} plans active on {date}: {', '.join(parts)}.",
            "meta": {"color_hint": "green" if not open_count else "yellow"},
        })

    for alert in alerts:
        blocks.append({
            "type": "warning",
            "label": alert["type"].replace("_", " ").title(),
            "value": alert["message"],
            "meta": {"severity": "medium", "plan_id": alert.get("plan_id")},
        })

    return {
        "date": date,
        "plan_count": len(plans),
        "total_orders": total_orders,
        "plans_by_state": plans_by_state,
        "orders_by_state": orders_by_state,
        "alerts": alerts,
        "blocks": blocks,
    }
```

---

## 3. `ai/tools/zone_tools.py` — Implement `evaluate_order_route_fit_tool`

Keep the existing `list_zones_tool` and `get_zone_snapshot_tool` stubs unchanged.
Add the full implementation of `evaluate_order_route_fit_tool`.

```python
from __future__ import annotations

from Delivery_app_BK.models import RouteSolution, Order, db
from Delivery_app_BK.services.context import ServiceContext
from .geometry_utils import (
    point_within_corridor,
    cheapest_insertion,
    eta_tolerance_to_buffer_m,
    meters_to_seconds,
)


# ── list_zones_tool / get_zone_snapshot_tool — KEEP AS STUBS (Phase 3) ────────

def list_zones_tool(ctx: ServiceContext, city_key: str | None = None) -> dict:
    raise NotImplementedError("list_zones_tool — Phase 3")


def get_zone_snapshot_tool(ctx: ServiceContext, zone_id: int, date: str | None = None) -> dict:
    raise NotImplementedError("get_zone_snapshot_tool — Phase 3")


# ── evaluate_order_route_fit_tool ─────────────────────────────────────────────

def evaluate_order_route_fit_tool(
    ctx: ServiceContext,
    route_solution_id: int,
    order_id: int,
) -> dict:
    """
    Evaluate whether adding *order_id* to *route_solution_id* is geographically
    feasible and operationally cheap.

    Spatial model: the route's corridor is a circle centered on the centroid of
    all current stop coordinates, with radius = max_stop_radius + eta_buffer.

    Returns a result dict with:
      - within_corridor (bool)
      - corridor_buffer_meters (float)
      - estimated_detour_meters (float)
      - estimated_detour_seconds (int)
      - best_insertion_index (int)
      - stop_count (int)
      - stop_coordinates_available (int)
      - blocks (list of NarrativeBlock dicts)
    """
    # ── Load route solution ───────────────────────────────────────────────────
    solution: RouteSolution | None = db.session.get(RouteSolution, route_solution_id)
    if solution is None or solution.team_id != ctx.team_id:
        return {"error": f"Route solution {route_solution_id} not found."}

    stops = sorted(solution.stops or [], key=lambda s: s.stop_order or 0)

    # ── Gather stop coordinates ───────────────────────────────────────────────
    stop_points: list[tuple[float, float]] = []
    for stop in stops:
        order: Order | None = db.session.get(Order, stop.order_id)
        if order is None:
            continue
        address = order.address if hasattr(order, "address") else getattr(order, "client_address", None)
        coords = (address or {}).get("coordinates")
        if coords and coords.get("lat") is not None and coords.get("lng") is not None:
            stop_points.append((float(coords["lat"]), float(coords["lng"])))

    # ── Load candidate order coordinates ─────────────────────────────────────
    candidate_order: Order | None = db.session.get(Order, order_id)
    if candidate_order is None or candidate_order.team_id != ctx.team_id:
        return {"error": f"Order {order_id} not found."}

    cand_address = (
        candidate_order.address
        if hasattr(candidate_order, "address")
        else getattr(candidate_order, "client_address", None)
    )
    cand_coords = (cand_address or {}).get("coordinates")
    if not cand_coords or cand_coords.get("lat") is None:
        return {
            "error": "Candidate order has no geocoded address. Run geocode_address first.",
            "order_id": order_id,
        }

    candidate_point = (float(cand_coords["lat"]), float(cand_coords["lng"]))

    # ── Corridor evaluation ───────────────────────────────────────────────────
    buffer_m = eta_tolerance_to_buffer_m(solution.eta_tolerance_seconds or 0)

    within = point_within_corridor(candidate_point, stop_points, buffer_m) if stop_points else False

    # ── Detour estimate ───────────────────────────────────────────────────────
    insertion = cheapest_insertion(stop_points, candidate_point) if stop_points else {
        "best_index": 0, "detour_meters": 0.0,
        "dist_to_prev_m": 0.0, "dist_to_next_m": 0.0,
    }
    detour_m = insertion["detour_meters"]
    detour_s = meters_to_seconds(detour_m)
    detour_min = round(detour_s / 60, 1)

    # ── Build NarrativeBlocks ─────────────────────────────────────────────────
    blocks = []

    blocks.append({
        "type": "stat_kpi",
        "label": "Within Corridor",
        "value": within,
        "meta": {
            "buffer_meters": round(buffer_m),
            "stop_coordinates_available": len(stop_points),
        },
    })

    blocks.append({
        "type": "stat_kpi",
        "label": "Estimated Detour",
        "value": detour_min,
        "meta": {
            "unit": "min",
            "meters": round(detour_m),
            "insert_before_stop": insertion["best_index"],
        },
    })

    if within and detour_min <= 5:
        blocks.append({
            "type": "insight",
            "label": "Route Fit",
            "value": (
                f"Order #{order_id} fits within the route corridor. "
                f"Cheapest insertion adds ~{detour_min} min."
            ),
            "meta": {"color_hint": "green"},
        })
    elif within:
        blocks.append({
            "type": "insight",
            "label": "Route Fit",
            "value": (
                f"Order #{order_id} is within the corridor but adds ~{detour_min} min to the route."
            ),
            "meta": {"color_hint": "yellow"},
        })
    else:
        blocks.append({
            "type": "warning",
            "label": "Outside Corridor",
            "value": (
                f"Order #{order_id} is outside the route corridor. "
                f"Adding it would add ~{detour_min} min and significant detour distance."
            ),
            "meta": {"severity": "medium", "color_hint": "orange"},
        })

    if not stop_points:
        blocks.append({
            "type": "warning",
            "label": "No Geocoded Stops",
            "value": "Route stops have no geocoded coordinates — corridor analysis is unavailable.",
            "meta": {"severity": "low"},
        })

    return {
        "route_solution_id": route_solution_id,
        "order_id": order_id,
        "within_corridor": within,
        "corridor_buffer_meters": round(buffer_m),
        "estimated_detour_meters": round(detour_m),
        "estimated_detour_seconds": detour_s,
        "best_insertion_index": insertion["best_index"],
        "stop_count": len(stops),
        "stop_coordinates_available": len(stop_points),
        "blocks": blocks,
    }
```

**Note on `order.address` vs `order.client_address`:**
The `Order` model uses `client_address` as the JSONB address field (based on
`AddressJSONValidationMixin` which validates `client_address`). The tool uses
`getattr(order, "client_address", None)` as the primary access pattern. Verify
the exact field name against the Order model before implementing — adjust if
the column name differs.

---

## 4. `ai/tool_registry.py` — Register 5 Tools

Uncomment/add exactly these entries. Do not enable any stubs (NotImplementedError tools).

```python
from Delivery_app_BK.ai.tools.narrative_tools import (
    get_plan_snapshot_tool,
    get_route_group_snapshot_tool,
    get_operations_dashboard_tool,
)
from Delivery_app_BK.ai.tools.zone_tools import evaluate_order_route_fit_tool
from Delivery_app_BK.ai.tools.geocode_tools import geocode_address_tool

TOOLS: dict[str, object] = {
    # ── Observation / narrative ────────────────────────────────────────────────
    "get_plan_snapshot":         get_plan_snapshot_tool,
    "get_route_group_snapshot":  get_route_group_snapshot_tool,
    "get_operations_dashboard":  get_operations_dashboard_tool,

    # ── Route corridor analysis ───────────────────────────────────────────────
    "evaluate_order_route_fit":  evaluate_order_route_fit_tool,

    # ── Geocoding (utility, pre-existing) ─────────────────────────────────────
    "geocode_address":           geocode_address_tool,
}
```

---

## 5. `ai/response_formatter.py` — Add Registry Entries

Add the following summary and action functions above the registry dicts,
then register them.

### Summary functions

```python
def _summarize_get_plan_snapshot(params: dict, result: dict) -> str:
    label = result.get("plan_label", f"plan #{params.get('plan_id', '?')}")
    total = result.get("total_orders", "?")
    groups = result.get("group_count", "?")
    return f"Plan '{label}': {total} orders across {groups} group(s)."


def _summarize_get_route_group_snapshot(params: dict, result: dict) -> str:
    zone = result.get("zone_name", "unknown group")
    total = result.get("total_orders", "?")
    state = result.get("state_name", "")
    return f"Route group '{zone}': {total} orders, state: {state}."


def _summarize_get_operations_dashboard(params: dict, result: dict) -> str:
    date = result.get("date", "?")
    plans = result.get("plan_count", "?")
    orders = result.get("total_orders", "?")
    return f"Operations on {date}: {plans} plan(s), {orders} orders."


def _summarize_evaluate_order_route_fit(params: dict, result: dict) -> str:
    order_id = result.get("order_id", params.get("order_id", "?"))
    within = result.get("within_corridor")
    detour_s = result.get("estimated_detour_seconds")
    detour_min = round(detour_s / 60, 1) if detour_s is not None else "?"
    fit_str = "fits within" if within else "is outside"
    return f"Order #{order_id} {fit_str} route corridor. Estimated detour: {detour_min} min."


def _summarize_geocode_address(params: dict, result: dict) -> str:
    found = result.get("found", False)
    q = params.get("q", "?")
    if found:
        formatted = result.get("formatted_address", q)
        return f"Geocoded '{q}' → '{formatted}'."
    return f"No geocoding result for '{q}'."
```

### Action functions

```python
def _actions_for_get_plan_snapshot(result: dict) -> list:
    plan_id = result.get("plan_id")
    if not plan_id:
        return []
    return [{
        "id": f"navigate_plan_{plan_id}",
        "type": "navigate",
        "label": "Open Plan",
        "payload": {"path": f"/plans/{plan_id}"},
    }]


def _actions_for_get_route_group_snapshot(result: dict) -> list:
    plan_id = result.get("route_plan_id")
    group_id = result.get("route_group_id")
    if not plan_id:
        return []
    path = f"/plans/{plan_id}" if not group_id else f"/plans/{plan_id}?group={group_id}"
    return [{
        "id": f"navigate_plan_{plan_id}",
        "type": "navigate",
        "label": "Open Route Group",
        "payload": {"path": path},
    }]


def _actions_for_get_operations_dashboard(result: dict) -> list:
    return [{
        "id": "navigate_plans",
        "type": "navigate",
        "label": "View Plans",
        "payload": {"path": "/plans"},
    }]


def _actions_for_evaluate_order_route_fit(result: dict) -> list:
    # No automatic navigation — the AI will suggest action based on fit result
    return []


def _actions_for_geocode_address(result: dict) -> list:
    return []
```

### Updated registries (replace the empty ones from Phase 1)

```python
_SUMMARY_REGISTRY: dict[str, Callable[[dict, dict], str]] = {
    "get_plan_snapshot":         _summarize_get_plan_snapshot,
    "get_route_group_snapshot":  _summarize_get_route_group_snapshot,
    "get_operations_dashboard":  _summarize_get_operations_dashboard,
    "evaluate_order_route_fit":  _summarize_evaluate_order_route_fit,
    "geocode_address":           _summarize_geocode_address,
}

_ACTION_REGISTRY: dict[str, Callable[[dict], list]] = {
    "get_plan_snapshot":         _actions_for_get_plan_snapshot,
    "get_route_group_snapshot":  _actions_for_get_route_group_snapshot,
    "get_operations_dashboard":  _actions_for_get_operations_dashboard,
    "evaluate_order_route_fit":  _actions_for_evaluate_order_route_fit,
    "geocode_address":           _actions_for_geocode_address,
}
```

---

## 6. `ai/prompts/system_prompt.py` — Add Tool Documentation

Replace the placeholder `AVAILABLE TOOLS` section with the following.
Everything else in the file remains unchanged.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── OBSERVATION TOOLS (read-only, no side effects) ──────────────────────────

get_plan_snapshot
  Returns a structured health view of a single plan: state, date window,
  total orders, per-group breakdown (zone name, order count, optimization status),
  item type counts, and synthesized warnings.
  Use when the user asks about a specific plan's status or readiness.

  Parameters:
    plan_id  (integer, required)  — the numeric ID of the plan

  Returns:
    plan_label, state_name, total_orders, group_count,
    has_unzoned_orders, unoptimized_group_count, blocks[]


get_route_group_snapshot
  Returns a detailed snapshot of a single route group: zone, order state
  distribution, active route health (stop count, distance, travel time,
  driver assignment), constraint violations, stale ETAs, and out-of-range stops.
  Use when the user asks about a specific route group or asks to inspect a route.

  Parameters:
    route_group_id  (integer, required)  — the numeric ID of the route group

  Returns:
    zone_name, route_plan_id, state_name, total_orders, has_active_route,
    driver_assigned, is_optimized, constraint_violations_count, blocks[]


get_operations_dashboard
  Returns a cross-plan summary for a given date: how many plans are active,
  total orders in the system, plans and orders broken down by state, and alerts
  for open plans or plans missing route groups.
  Use when the user asks about "today's operations", "what's happening", or
  asks for a broad status overview without specifying a plan.

  Parameters:
    date  (ISO date string, optional)  — default: today (UTC)
          Format: "YYYY-MM-DD"

  Returns:
    date, plan_count, total_orders, plans_by_state, orders_by_state,
    alerts[], blocks[]


evaluate_order_route_fit
  Evaluates whether adding a candidate order to an existing route solution
  is geographically feasible and operationally cheap.

  Corridor model: centroid of current stop coordinates + buffer derived from
  the route's eta_tolerance_seconds. Returns within_corridor (bool),
  estimated detour (minutes), and best insertion index.

  Use when the user asks: "Can I add order X to route Y?", "Is this order
  on the way?", or "Would adding this order impact the route significantly?"

  PREREQUISITE: the candidate order must have a geocoded address (coordinates).
  If order has no coordinates, call geocode_address first.

  Parameters:
    route_solution_id  (integer, required)  — the numeric ID of the route solution
    order_id           (integer, required)  — the numeric ID of the candidate order

  Returns:
    within_corridor, corridor_buffer_meters, estimated_detour_meters,
    estimated_detour_seconds, best_insertion_index, stop_count,
    stop_coordinates_available, blocks[]


── UTILITY TOOLS ────────────────────────────────────────────────────────────

geocode_address
  Resolves a free-text address string to a structured address object
  matching ADDRESS_SCHEMA (street_address, city, country, coordinates.lat/lng).

  ALWAYS call this before create_order or evaluate_order_route_fit when the
  user provides an address as plain text. Pass the returned address_object
  directly as client_address.

  Parameters:
    q             (string, required)   — free-text address string
    country_hint  (string, optional)   — ISO 3166-1 alpha-2 code (e.g. "SE")
                                         Always set when team's country is known.

  Returns:
    found (bool), formatted_address, address_object (or null if not found),
    used_country_hint, hint (guidance string if not found)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 7. `ai/AI_OPERATOR.md` — Update

Update the following sections only. All infrastructure sections remain unchanged.

### Registered Tools table — replace with:

| Tool name | File | Domain service |
|---|---|---|
| `get_plan_snapshot` | `tools/narrative_tools.py` | `queries/route_plan/get_plan.py` + `route_groups/list_route_groups.py` |
| `get_route_group_snapshot` | `tools/narrative_tools.py` | `queries/route_plan/route_groups/get_route_group.py` |
| `get_operations_dashboard` | `tools/narrative_tools.py` | `queries/route_plan/find_plans.py` |
| `evaluate_order_route_fit` | `tools/zone_tools.py` | direct `RouteSolution` + `Order` query + `tools/geometry_utils.py` |
| `geocode_address` | `tools/geocode_tools.py` | `geocoding/orchestrator.py` |

### Module Structure — add new files:

```
ai/tools/
  narrative_tools.py    ← IMPLEMENTED: get_plan_snapshot, get_route_group_snapshot,
                                        get_operations_dashboard
  zone_tools.py         ← PARTIAL: evaluate_order_route_fit implemented;
                                    list_zones, get_zone_snapshot are Phase 3 stubs
  geocode_tools.py      ← IMPLEMENTED (pre-existing): geocode_address_tool
  geometry_utils.py     ← NEW: haversine, centroid, corridor, cheapest_insertion
```

---

## Verification Checklist

- [ ] `from Delivery_app_BK.ai.tools.geometry_utils import haversine_m, point_within_corridor, cheapest_insertion` — importable, no side effects
- [ ] `haversine_m(59.33, 18.07, 59.34, 18.08)` returns a positive float (≈ ~1100 m)
- [ ] `point_within_corridor((59.335, 18.075), [(59.33, 18.07), (59.34, 18.08)], 500)` returns `True`
- [ ] `cheapest_insertion([(0,0),(1,1),(2,2)], (1,0))` returns a dict with `best_index` and `detour_meters`
- [ ] `from Delivery_app_BK.ai.tool_registry import TOOLS` — has exactly 5 keys
- [ ] `TOOLS` keys: `{"get_plan_snapshot", "get_route_group_snapshot", "get_operations_dashboard", "evaluate_order_route_fit", "geocode_address"}`
- [ ] `_SUMMARY_REGISTRY` in `response_formatter.py` has 5 entries (matching TOOLS keys)
- [ ] `_ACTION_REGISTRY` in `response_formatter.py` has 5 entries (matching TOOLS keys)
- [ ] `build_system_prompt()` output contains the string `"get_plan_snapshot"`
- [ ] `build_system_prompt()` output contains the string `"evaluate_order_route_fit"`
- [ ] `get_plan_snapshot_tool` — calling with a valid plan_id returns a dict with `"blocks"` key (list)
- [ ] `get_route_group_snapshot_tool` — calling with a valid route_group_id returns a dict with `"blocks"` key
- [ ] `get_operations_dashboard_tool` — calling with no args returns a dict with `"blocks"` key
- [ ] `evaluate_order_route_fit_tool` — calling with invalid IDs returns `{"error": "..."}`, not an exception
- [ ] `list_zones_tool` and `get_zone_snapshot_tool` still raise `NotImplementedError` (stubs untouched)
- [ ] All `NarrativeBlock` dicts in tool results have valid `type` values matching the Literal in `schemas.py`
- [ ] `ai/tools/geocode_tools.py` is NOT modified
- [ ] `orchestrator.py`, `planner.py`, `thread_store.py`, `errors.py`, `schemas.py`, `providers/*` are untouched

---

## What This Phase Does NOT Do

- Does not implement `list_orders`, `list_plans`, `list_route_groups`, `list_zones` (Phase 3)
- Does not implement any mutation tools (Phase 4)
- Does not implement `get_zone_snapshot_tool` or `list_zones_tool` (Phase 3)
- Does not modify any model, migration, or router
- Does not change the AI thread HTTP endpoints

---

## Next Phase Preview

**Phase 3 — Core Query Tools** will implement:
- `list_orders` — with all new filters (route_group_id, operation_type, order_plan_objective, zone_id via OrderZoneAssignment join)
- `list_plans` — updated for RoutePlan with zone/group awareness
- `list_route_groups` — exposes groups as a navigable resource for the AI
- `list_zones` — lists active zones for the team
- `get_zone_snapshot` — zone-level health view (order density, capacity vs. template limits)
