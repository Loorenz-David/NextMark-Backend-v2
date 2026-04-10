from Delivery_app_BK.models import RouteGroup, db
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import get_route_freshness_updated_at
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ROUTE_GROUP_UPDATED,
)
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room, build_team_members_room


def emit_route_group_updated(route_group: RouteGroup, *, payload: dict | None = None) -> None:
    """Emit RouteGroup updated event. Broadcast to team_orders (admin visibility) and team_members (driver notification)."""
    if not route_group or not route_group.route_plan_id:
        return

    persisted_route_group = db.session.get(RouteGroup, route_group.id)
    if not persisted_route_group or not persisted_route_group.route_plan:
        return
    route_plan = persisted_route_group.route_plan

    team_id = route_group.team_id
    route_group_id = route_group.id
    route_plan_id = route_group.route_plan_id

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_GROUP_UPDATED,
        occurred_at=None,
        team_id=team_id,
        entity_type="route_group",
        entity_id=route_group.id,
        payload={
            "route_group_id": route_group_id,
            "route_plan_id": route_plan_id,
            "label": route_plan.label,
            "route_freshness_updated_at": get_route_freshness_updated_at(route_plan),
            **(payload or {}),
        },
    )

    # Broadcast to team_admin room (admin visibility)
    emit_business_event(room=build_team_admin_room(team_id), envelope=envelope)
    # Broadcast to team_members room (driver notification)
    emit_business_event(room=build_team_members_room(team_id), envelope=envelope)
    notify_delivery_planning_event(
        event_id=envelope["event_id"],
        event_name=BUSINESS_EVENT_ROUTE_GROUP_UPDATED,
        team_id=team_id,
        entity_type="route_group",
        entity_id=route_group.id,
        payload=envelope["payload"],
        occurred_at=envelope["occurred_at"],
        actor=None,
    )
