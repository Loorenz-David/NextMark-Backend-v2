from datetime import date
from typing import Optional, List, Dict, Any

from Delivery_app_BK.models import db, RouteGroup, RoutePlan, RouteSolution


def check_vehicle_availability(
    vehicle_id: int,
    start_date: date,
    end_date: date,
    exclude_route_solution_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns conflicting selected route solutions for the given vehicle and date window.

    Conflict criteria:
    - route_solution.vehicle_id = vehicle_id
    - route_solution.is_selected = True
    - route_plan date window overlaps: existing.start_date <= query.end_date
                                   AND existing.end_date   >= query.start_date
    - route_solution.id != exclude_route_solution_id (if provided)
    """
    query = (
        db.session.query(
            RouteSolution.id.label("route_solution_id"),
            RoutePlan.id.label("route_plan_id"),
            RoutePlan.label.label("route_plan_label"),
            RoutePlan.start_date.label("start_date"),
            RoutePlan.end_date.label("end_date"),
        )
        .join(RouteGroup, RouteSolution.route_group_id == RouteGroup.id)
        .join(RoutePlan, RouteGroup.route_plan_id == RoutePlan.id)
        .filter(RouteSolution.vehicle_id == vehicle_id)
        .filter(RouteSolution.is_selected == True)  # noqa: E712
        # Standard date-overlap check:
        # existing window starts before or on query end_date
        .filter(RoutePlan.start_date <= end_date)
        # existing window ends on or after query start_date
        .filter(RoutePlan.end_date >= start_date)
    )

    if exclude_route_solution_id is not None:
        query = query.filter(RouteSolution.id != exclude_route_solution_id)

    rows = query.all()

    return [
        {
            "route_solution_id": row.route_solution_id,
            "route_plan_id": row.route_plan_id,
            "route_plan_label": row.route_plan_label,
            "start_date": row.start_date.strftime("%Y-%m-%d") if row.start_date else None,
            "end_date": row.end_date.strftime("%Y-%m-%d") if row.end_date else None,
        }
        for row in rows
    ]
