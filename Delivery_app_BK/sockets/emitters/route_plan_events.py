"""Socket emitters for RoutePlan-level events."""
from __future__ import annotations
from typing import TYPE_CHECKING

from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_PLAN_UPDATED
from Delivery_app_BK.sockets.emitters.common import build_business_event_envelope, emit_business_event
from Delivery_app_BK.sockets.rooms.names import build_team_admin_room

if TYPE_CHECKING:
    from Delivery_app_BK.models import RoutePlan


def emit_delivery_plan_totals_updated(plan: "RoutePlan") -> None:
    """Broadcast updated plan totals to every admin in the team room."""
    if plan is None or plan.id is None or plan.team_id is None:
        return

    envelope = build_business_event_envelope(
        event_name=BUSINESS_EVENT_ROUTE_PLAN_UPDATED,
        team_id=plan.team_id,
        entity_type="route_plan",
        entity_id=plan.id,
        payload={
            "route_plan_id": plan.id,
            "total_weight": plan.total_weight_g,
            "total_volume": plan.total_volume_cm3,
            "total_items": plan.total_item_count,
            "total_orders": plan.total_orders,
        },
    )
    emit_business_event(room=build_team_admin_room(plan.team_id), envelope=envelope)
