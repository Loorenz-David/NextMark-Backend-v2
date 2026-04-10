from __future__ import annotations

from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import db, RouteSolution
from Delivery_app_BK.models.tables.delivery_plan.delivery_plan import DeliveryPlan
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solution_stops import (
    serialize_route_solution_stops,
)


def get_execution_status(ctx: ServiceContext, plan: DeliveryPlan) -> dict:
    """
    Return the active route and driver info for a local_delivery plan.
    Queries the is_selected=True RouteSolution for the given plan,
    and returns its stops, driver, vehicle, and timing information.
    """
    route = (
        db.session.query(RouteSolution)
        .options(
            selectinload(RouteSolution.driver),
            selectinload(RouteSolution.local_delivery_plan),
        )
        .filter(
            RouteSolution.local_delivery_plan_id == plan.id,
            RouteSolution.is_selected.is_(True),
        )
        .first()
    )

    if not route:
        return {
            "status": "no_route_selected",
            "plan_id": plan.id,
            "plan_type": plan.plan_type,
        }

    stops_raw = list(route.stops or [])
    stops = serialize_route_solution_stops(stops_raw, ctx)

    return {
        "status": "ok",
        "plan_id": plan.id,
        "plan_type": plan.plan_type,
        "route_id": route.id,
        "label": route.label,
        "driver_id": route.driver_id,
        "driver_name": route.driver.username if route.driver else None,
        "plan_label": route.local_delivery_plan.label if route.local_delivery_plan else plan.label,
        "vehicle_id": route.vehicle_id,
        "is_optimized": route.is_optimized,
        "total_distance_meters": route.total_distance_meters,
        "total_travel_time_seconds": route.total_travel_time_seconds,
        "expected_start_time": route.expected_start_time.isoformat() if route.expected_start_time else None,
        "expected_end_time": route.expected_end_time.isoformat() if route.expected_end_time else None,
        "actual_start_time": route.actual_start_time.isoformat() if route.actual_start_time else None,
        "actual_end_time": route.actual_end_time.isoformat() if route.actual_end_time else None,
        "stops_count": len(stops_raw),
        "stops": stops,
    }
