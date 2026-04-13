from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app

from Delivery_app_BK.models import Order, RouteSolutionStop, RouteSolution, RouteGroup, Team, db
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import get_route_freshness_updated_at
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room, build_team_members_room


def emit_route_solution_stop_updated(route_solution_stop: RouteSolutionStop, *, payload: dict | None = None) -> None:
    """Emit RouteSolutionStop updated event. Broadcast to team_orders (admin visibility) and team_members (driver notification)."""
    if not route_solution_stop or not route_solution_stop.route_solution_id:
        current_app.logger.warning("Cannot emit route_solution_stop.updated: missing route_solution_stop or route_solution_id")
        return

    route_solution = db.session.get(RouteSolution, route_solution_stop.route_solution_id)
    route_group_id = getattr(route_solution, "route_group_id", None) if route_solution is not None else None
    if not route_solution or not route_group_id:
        current_app.logger.warning(
            "Cannot emit route_solution_stop.updated: missing route_solution (solution_id=%s)",
            route_solution_stop.route_solution_id
        )
        return

    route_group = db.session.get(RouteGroup, route_group_id)
    if not route_group or not route_group.route_plan_id:
        current_app.logger.warning(
            "Cannot emit route_solution_stop.updated: missing route_group (route_group_id=%s)",
            route_group_id
        )
        return

    team_id = route_solution_stop.team_id
    route_plan_id = route_group.route_plan_id

    order = db.session.get(Order, route_solution_stop.order_id) if route_solution_stop.order_id else None
    team = db.session.get(Team, team_id) if team_id else None
    tz_str = getattr(team, "time_zone", None) or "UTC"

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
        occurred_at=None,
        team_id=team_id,
        entity_type="route_solution_stop",
        entity_id=route_solution_stop.id,
        payload={
            "route_solution_stop_id": route_solution_stop.id,
            "route_solution_id": route_solution_stop.route_solution_id,
            **_plan_id_aliases(route_group_id=route_group_id, route_plan_id=route_plan_id),
            "label": route_solution.label,
            "route_freshness_updated_at": get_route_freshness_updated_at(route_group.route_plan),
            "driver_id": route_solution.driver_id,
            "order_id": route_solution_stop.order_id,
            "stop_order": route_solution_stop.stop_order,
            "expected_arrival_time": route_solution_stop.expected_arrival_time.isoformat() if route_solution_stop.expected_arrival_time else None,
            "expected_departure_time": route_solution_stop.expected_departure_time.isoformat() if route_solution_stop.expected_departure_time else None,
            "actual_arrival_time": route_solution_stop.actual_arrival_time.isoformat() if route_solution_stop.actual_arrival_time else None,
            "actual_departure_time": route_solution_stop.actual_departure_time.isoformat() if route_solution_stop.actual_departure_time else None,
            "notification_client_label": _build_stop_client_label(order),
            "notification_arrival_label": _format_stop_arrival_label(route_solution_stop.expected_arrival_time, tz_str),
            **(payload or {}),
        },
    )

    # Broadcast to team_admin room (admin visibility)
    emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    # Broadcast to team_members room (driver notification)
    emit_business_event(room=build_team_members_room(team_id), envelope=envelope)
    # Also broadcast to order room for order-specific listeners
    emit_business_event(room=f"order:{route_solution_stop.order_id}", envelope=envelope)
    notify_delivery_planning_event(
        event_id=envelope["event_id"],
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
        team_id=team_id,
        entity_type="route_solution_stop",
        entity_id=route_solution_stop.id,
        payload=envelope["payload"],
        occurred_at=envelope["occurred_at"],
        actor=None,
    )
    
    current_app.logger.info(
        "Emitted route_solution_stop.updated: stop_id=%d, route_id=%d, order_id=%d, team_id=%d",
        route_solution_stop.id, route_solution_stop.route_solution_id, route_solution_stop.order_id, team_id
    )


def _plan_id_aliases(*, route_group_id: int, route_plan_id: int) -> dict:
    return {
        "route_group_id": route_group_id,
        "route_plan_id": route_plan_id,
    }


def _build_stop_client_label(order: Order | None) -> str | None:
    if order is None:
        return None
    first = (getattr(order, "client_first_name", None) or "").strip()
    last = (getattr(order, "client_last_name", None) or "").strip()
    if first or last:
        parts = [first] if first else []
        if last:
            parts.append(last[0].upper() + ".")
        return " ".join(parts)
    scalar_id = getattr(order, "order_scalar_id", None)
    if isinstance(scalar_id, int):
        return f"Order #{scalar_id}"
    return None


def _format_stop_arrival_label(arrival_time: datetime | None, tz_str: str) -> str | None:
    if arrival_time is None:
        return None
    try:
        local = arrival_time.astimezone(ZoneInfo(tz_str))
        now = datetime.now(local.tzinfo)
        time_str = local.strftime("%H:%M")
        if local.date() == now.date():
            return f"today {time_str}"
        return f"{local.strftime('%b')} {local.day} {time_str}"
    except Exception:
        return None
