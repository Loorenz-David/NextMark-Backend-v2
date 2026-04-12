from flask import current_app

from Delivery_app_BK.models import RouteSolution, RouteGroup, db
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)
from Delivery_app_BK.services.domain.delivery_plan.plan.route_freshness import get_route_freshness_updated_at
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ROUTE_SOLUTION_CREATED,
    BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
    BUSINESS_EVENT_ROUTE_SOLUTION_DELETED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room, build_team_members_room

def emit_route_solution_created(route_solution: RouteSolution, *, payload: dict | None = None) -> None:
    """Emit RouteSolution created event. Broadcast to team_orders (admin visibility) and team_members (driver notification)."""
    route_group_id = getattr(route_solution, "route_group_id", None)
    if route_group_id is None:
        route_group_id = getattr(route_solution, "local_delivery_plan_id", None)
    if not route_solution or not route_group_id:
        current_app.logger.warning("Cannot emit route_solution.created: missing route_solution or route_group_id")
        return

    route_group = db.session.get(RouteGroup, route_group_id)
    if not route_group or not route_group.route_plan_id:
        current_app.logger.warning(
            "Cannot emit route_solution.created: missing route_group (route_group_id=%s)",
            route_group_id
        )
        return

    team_id = route_solution.team_id
    route_plan_id = route_group.route_plan_id

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_CREATED,
        occurred_at=route_solution.created_at,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution.id,
        payload={
            "route_solution_id": route_solution.id,
            **_plan_id_aliases(route_group_id=route_group_id, route_plan_id=route_plan_id),
            "label": route_solution.label,
            "plan_label": route_group.route_plan.label if route_group.route_plan else None,
            "plan_type": resolve_route_plan_workflow_type(),
            "route_freshness_updated_at": get_route_freshness_updated_at(route_group.route_plan),
            "is_selected": route_solution.is_selected,
            "driver_id": route_solution.driver_id,
            **(payload or {}),
        },
    )
    current_app.logger.info(
        "route_solution.created fanout | solution_id=%s team_id=%s assigned_driver_id=%s payload=%s",
        route_solution.id,
        team_id,
        route_solution.driver_id,
        envelope["payload"],
    )

    # Broadcast to team_admin room (admin visibility)
    emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    # Broadcast to team_members room (driver notification)
    emit_business_event(room=build_team_members_room(team_id), envelope=envelope)
    notify_delivery_planning_event(
        event_id=envelope["event_id"],
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_CREATED,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution.id,
        payload=envelope["payload"],
        occurred_at=envelope["occurred_at"],
        actor=None,
    )
    current_app.logger.info("Emitted route_solution.created: solution_id=%d, team_id=%d", route_solution.id, team_id)


def emit_route_solution_updated(route_solution: RouteSolution, *, payload: dict | None = None) -> None:
    """Emit RouteSolution updated event. Broadcast to team_orders (admin visibility) and team_members (driver notification)."""
    route_group_id = getattr(route_solution, "route_group_id", None)
    if route_group_id is None:
        route_group_id = getattr(route_solution, "local_delivery_plan_id", None)
    if not route_solution or not route_group_id:
        current_app.logger.warning("Cannot emit route_solution.updated: missing route_solution or route_group_id")
        return

    route_group = db.session.get(RouteGroup, route_group_id)
    if not route_group or not route_group.route_plan_id:
        current_app.logger.warning(
            "Cannot emit route_solution.updated: missing route_group (route_group_id=%s)",
            route_group_id
        )
        return

    team_id = route_solution.team_id
    route_plan_id = route_group.route_plan_id

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
        occurred_at=None,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution.id,
        payload={
            "route_solution_id": route_solution.id,
            **_plan_id_aliases(route_group_id=route_group_id, route_plan_id=route_plan_id),
            "label": route_solution.label,
            "plan_label": route_group.route_plan.label if route_group.route_plan else None,
            "plan_type": resolve_route_plan_workflow_type(),
            "route_freshness_updated_at": get_route_freshness_updated_at(route_group.route_plan),
            "is_selected": route_solution.is_selected,
            "driver_id": route_solution.driver_id,
            "expected_start_time": route_solution.expected_start_time.isoformat() if route_solution.expected_start_time else None,
            "expected_end_time": route_solution.expected_end_time.isoformat() if route_solution.expected_end_time else None,
            **(payload or {}),
        },
    )

    # Broadcast to team_admin room (admin visibility)
    emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    # Broadcast to team_members room (driver notification)
    emit_business_event(room=build_team_members_room(team_id), envelope=envelope)
    notify_delivery_planning_event(
        event_id=envelope["event_id"],
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution.id,
        payload=envelope["payload"],
        occurred_at=envelope["occurred_at"],
        actor=None,
    )
    current_app.logger.info("Emitted route_solution.updated: solution_id=%d, team_id=%d", route_solution.id, team_id)


def emit_route_solution_deleted_for_route_group(
    team_id: int,
    route_group_id: int,
    route_solution_id: int,
    *,
    payload: dict | None = None,
) -> None:
    """Emit RouteSolution deleted event. Broadcast to team_orders (admin visibility) and team_members (driver notification)."""
    if not team_id or not route_group_id or not route_solution_id:
        current_app.logger.warning(
            "Cannot emit route_solution.deleted: missing team_id, route_group_id, or route_solution_id"
        )
        return

    route_group = db.session.get(RouteGroup, route_group_id)
    if not route_group or not route_group.route_plan_id:
        current_app.logger.warning(
            "Cannot emit route_solution.deleted: missing route_group (route_group_id=%s)",
            route_group_id
        )
        return

    route_plan_id = route_group.route_plan_id

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_DELETED,
        occurred_at=None,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution_id,
        payload={
            "route_solution_id": route_solution_id,
            **_plan_id_aliases(route_group_id=route_group_id, route_plan_id=route_plan_id),
            "route_freshness_updated_at": get_route_freshness_updated_at(route_group.route_plan),
            **(payload or {}),
        },
    )

    # Broadcast to team_admin room (admin visibility)
    emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    # Broadcast to team_members room (driver notification)
    emit_business_event(room=build_team_members_room(team_id), envelope=envelope)
    notify_delivery_planning_event(
        event_id=envelope["event_id"],
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_DELETED,
        team_id=team_id,
        entity_type="route_solution",
        entity_id=route_solution_id,
        payload=envelope["payload"],
        occurred_at=envelope["occurred_at"],
        actor=None,
    )
    current_app.logger.info("Emitted route_solution.deleted: solution_id=%d, team_id=%d", route_solution_id, team_id)


def emit_route_solution_deleted(team_id: int, local_delivery_plan_id: int, route_solution_id: int, *, payload: dict | None = None) -> None:
    """Backward-compatible wrapper for legacy callsites passing local_delivery_plan_id."""
    emit_route_solution_deleted_for_route_group(
        team_id=team_id,
        route_group_id=local_delivery_plan_id,
        route_solution_id=route_solution_id,
        payload=payload,
    )


def _plan_id_aliases(*, route_group_id: int, route_plan_id: int) -> dict:
    return {
        "route_group_id": route_group_id,
        "route_plan_id": route_plan_id,
        # Backward-compatible payload keys while route naming migration is active.
        "local_delivery_plan_id": route_group_id,
        "delivery_plan_id": route_plan_id,
    }
