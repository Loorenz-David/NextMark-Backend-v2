"""Remove a route group from a plan, provided it has not been executed."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import RouteGroup, RouteSolution, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import recompute_plan_totals


def delete_route_group(ctx: ServiceContext) -> dict:
    route_group_id = ctx.incoming_data.get("route_group_id")
    route_plan_id = ctx.incoming_data.get("route_plan_id")

    if not route_group_id:
        raise ValidationFailed("route_group_id is required")

    route_group = db.session.get(RouteGroup, route_group_id)
    if route_group is None or route_group.team_id != ctx.team_id:
        raise NotFound(f"Route group {route_group_id} not found")

    if route_plan_id is not None and route_group.route_plan_id != route_plan_id:
        raise NotFound(f"Route group {route_group_id} not found")

    if route_group.zone_id is None and getattr(route_group, "is_system_default_bucket", False):
        raise ValidationFailed(
            "The no-zone route group cannot be deleted. It is a system-managed group present on every plan."
        )

    has_executed_selected_solution = (
        RouteSolution.query.filter(
            RouteSolution.route_group_id == route_group.id,
            RouteSolution.is_selected.is_(True),
            RouteSolution.actual_start_time.isnot(None),
        ).count()
        > 0
    )
    if has_executed_selected_solution:
        raise ValidationFailed(
            "Cannot remove a route group with an in-progress or completed route solution."
        )

    route_plan = route_group.route_plan
    db.session.delete(route_group)
    if route_plan is not None:
        recompute_plan_totals(route_plan)
    db.session.commit()

    return {
        "deleted": True,
        "route_group_id": route_group_id,
    }
