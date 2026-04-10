"""
Narrative / observation tools.
These tools synthesize aggregated data into NarrativeBlock lists.
They do NOT mutate state.

Implements: get_plan_snapshot, get_route_group_snapshot, get_operations_dashboard.

Status: IMPLEMENTED — Phase 2.
"""
from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import RouteGroup, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.find_plans import find_plans
from Delivery_app_BK.services.queries.route_plan.get_plan import get_plan
from Delivery_app_BK.services.queries.route_plan.route_groups.get_route_group import (
    get_route_group,
)
from Delivery_app_BK.services.queries.route_plan.route_groups.list_route_groups import (
    list_route_groups,
)

from Delivery_app_BK.ai.prompts.system_prompt import ORDER_STATE_MAP, PLAN_STATE_MAP

# ── Reverse maps: integer state_id → state name ───────────────────────────────
_ORDER_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in ORDER_STATE_MAP.items()}
_PLAN_STATE_ID_TO_NAME: dict[int, str] = {v: k for k, v in PLAN_STATE_MAP.items()}


def _state_counts_to_named(raw: dict | None) -> dict[str, int]:
    """Convert {str(state_id) | int: count} → {state_name: count}."""
    if not raw:
        return {}
    result: dict[str, int] = {}
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


# ── Tools ─────────────────────────────────────────────────────────────────────

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


def get_route_group_snapshot_tool(ctx: ServiceContext, route_group_id: int) -> dict:
    """
    Returns a detailed snapshot of a single route group:
      - zone info and template constraints
      - order state distribution
      - active route: driver, stop count, distance, travel time
      - warnings: constraint violations, stale ETAs, out-of-range stops
    Result includes a 'blocks' list of NarrativeBlock dicts.
    """
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
    state_id = (rg.get("state") or {}).get("id")
    state_name = _plan_state_name(state_id)
    total_orders = rg.get("total_orders") or 0
    order_state_counts = _state_counts_to_named(rg.get("order_state_counts"))
    item_type_counts = rg.get("item_type_counts") or {}

    has_active_route = selected_solution is not None
    driver_id = (selected_solution or {}).get("driver_id")
    driver_name = (selected_solution or {}).get("driver_name")
    is_optimized = (selected_solution or {}).get("is_optimized", "not_optimized")
    total_distance_m = (selected_solution or {}).get("total_distance_meters")
    total_travel_s = (selected_solution or {}).get("total_travel_time_seconds")

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

    if has_active_route and not driver_id:
        blocks.append({
            "type": "warning",
            "label": "No Driver",
            "value": "Active route has no driver assigned.",
            "meta": {"severity": "high"},
        })

    if has_active_route and is_optimized == "not_optimized":
        blocks.append({
            "type": "warning",
            "label": "Not Optimized",
            "value": "Route solution exists but has not been optimized.",
            "meta": {"severity": "medium"},
        })

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
    plans = query.all()

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

        for group in (plan.route_groups or []):
            named = _state_counts_to_named(getattr(group, "order_state_counts", None))
            for sname, cnt in named.items():
                orders_by_state[sname] = orders_by_state.get(sname, 0) + cnt

        if plan.state_id == 1 and (plan.total_orders or 0) > 0:
            alerts.append({
                "type": "open_plan_with_orders",
                "message": f"Plan '{plan.label}' is still Open with {plan.total_orders} orders.",
                "plan_id": plan.id,
            })

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
