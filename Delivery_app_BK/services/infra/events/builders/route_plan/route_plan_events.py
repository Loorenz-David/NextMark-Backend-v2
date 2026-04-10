from datetime import datetime

from Delivery_app_BK.services.domain.route_operations.plan.plan_events import RoutePlanEvent


def build_route_plan_rescheduled_event(
    route_plan_id: int,
    old_start_date: datetime | None,
    old_end_date: datetime | None,
    new_start_date: datetime | None,
    new_end_date: datetime | None,
) -> dict:
    return {
        "route_plan_id": route_plan_id,
        "event_name": RoutePlanEvent.DELIVERY_PLAN_RESCHEDULED.value,
        "payload": {
            "route_plan_id": route_plan_id,
            "old_start_date": old_start_date.isoformat() if old_start_date else None,
            "old_end_date": old_end_date.isoformat() if old_end_date else None,
            "new_start_date": new_start_date.isoformat() if new_start_date else None,
            "new_end_date": new_end_date.isoformat() if new_end_date else None,
        },
    }
