"""
Zone-domain tools.
Implements: list_zones, get_zone_snapshot, evaluate_order_route_fit.

Status: PARTIAL — evaluate_order_route_fit implemented (Phase 2).
        list_zones and get_zone_snapshot are Phase 3 stubs.
"""
from __future__ import annotations

from Delivery_app_BK.models import (
    Order,
    OrderZoneAssignment,
    RouteGroup,
    RouteSolution,
    Zone,
    ZoneTemplate,
    db,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.find_zones import find_zones
from Delivery_app_BK.services.queries.zones.serialize_zone_template import (
    serialize_zone_template,
)

from .geometry_utils import (
    cheapest_insertion,
    eta_tolerance_to_buffer_m,
    meters_to_seconds,
    point_within_corridor,
)

AI_ZONE_LIMIT = 50


# ── Phase 3 stubs ──────────────────────────────────────────────────────────────

def list_zones_tool(ctx: ServiceContext, city_key: str | None = None) -> dict:
    """
    Lists active zones for the team. Returns zone identity, centroid,
    and key template constraints.
    """
    params: dict = {
        "is_active": True,
        "sort": "id_asc",
        "limit": AI_ZONE_LIMIT,
    }
    if ctx.team_id:
        params["team_id"] = ctx.team_id
    if city_key:
        params["city_key"] = city_key.strip()

    tool_ctx = ServiceContext(query_params=params, identity=ctx.identity)
    query = find_zones(params, tool_ctx)
    zones = query.limit(AI_ZONE_LIMIT + 1).all()
    has_more = len(zones) > AI_ZONE_LIMIT
    page = zones[:AI_ZONE_LIMIT]

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


def get_zone_snapshot_tool(ctx: ServiceContext, zone_id: int, date: str | None = None) -> dict:
    """
    Returns a strategic snapshot of a zone including capacity and route group usage.
    """
    from Delivery_app_BK.ai.tools.narrative_tools import _plan_state_name

    zone: Zone | None = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id:
        return {"error": f"Zone {zone_id} not found."}

    template = ZoneTemplate.query.filter_by(
        team_id=ctx.team_id, zone_id=zone_id, is_active=True
    ).first()
    tmpl_data = serialize_zone_template(template) if template else {}

    max_orders_per_route = tmpl_data.get("max_orders_per_route")
    max_vehicles = tmpl_data.get("max_vehicles")
    op_start = tmpl_data.get("operating_window_start")
    op_end = tmpl_data.get("operating_window_end")
    eta_tolerance_s = tmpl_data.get("eta_tolerance_seconds", 0)

    assigned_order_count: int = (
        db.session.query(db.func.count(OrderZoneAssignment.id))
        .filter(
            OrderZoneAssignment.team_id == ctx.team_id,
            OrderZoneAssignment.zone_id == zone_id,
            OrderZoneAssignment.is_unassigned.is_(False),
        )
        .scalar()
    ) or 0

    unassigned_count: int = (
        db.session.query(db.func.count(OrderZoneAssignment.id))
        .filter(
            OrderZoneAssignment.team_id == ctx.team_id,
            OrderZoneAssignment.city_key == zone.city_key,
            OrderZoneAssignment.is_unassigned.is_(True),
        )
        .scalar()
    ) or 0

    route_groups = (
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

    max_capacity = None
    utilization_pct = None
    if max_orders_per_route and max_vehicles:
        max_capacity = max_orders_per_route * max_vehicles
        utilization_pct = round(assigned_order_count / max_capacity * 100, 1) if max_capacity else None

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
            "value": f"{op_start} - {op_end}",
            "meta": {"eta_tolerance_seconds": eta_tolerance_s},
        })

    if group_summaries:
        blocks.append({
            "type": "stat_breakdown",
            "label": f"Route Groups ({len(group_summaries)})",
            "value": group_summaries,
            "meta": {"format": "group_list"},
        })

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
        caddr = getattr(order, "client_address", None) or {}
        coords = caddr.get("coordinates") if isinstance(caddr, dict) else None
        if coords and coords.get("lat") is not None and coords.get("lng") is not None:
            stop_points.append((float(coords["lat"]), float(coords["lng"])))

    # ── Load candidate order ──────────────────────────────────────────────────
    candidate_order: Order | None = db.session.get(Order, order_id)
    if candidate_order is None or candidate_order.team_id != ctx.team_id:
        return {"error": f"Order {order_id} not found."}

    cand_addr = getattr(candidate_order, "client_address", None) or {}
    cand_coords = cand_addr.get("coordinates") if isinstance(cand_addr, dict) else None
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
    if stop_points:
        insertion = cheapest_insertion(stop_points, candidate_point)
    else:
        insertion = {"best_index": 0, "detour_meters": 0.0, "dist_to_prev_m": 0.0, "dist_to_next_m": 0.0}

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
