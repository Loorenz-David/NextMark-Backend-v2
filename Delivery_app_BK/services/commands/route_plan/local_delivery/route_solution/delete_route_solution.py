from __future__ import annotations

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteSolution, db
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    ensure_single_selected_route_solution,
)

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance


def delete_route_solution(ctx: ServiceContext):
    incoming_data = ctx.incoming_data or {}
    route_solution_id = incoming_data.get("route_solution_id")
    if not route_solution_id:
        raise ValidationFailed("route_solution_id is required.")

    route_solution = get_instance(ctx=ctx, model=RouteSolution, value=route_solution_id)
    route_group_id = route_solution.route_group_id
    db.session.delete(route_solution)
    db.session.flush()
    ensure_single_selected_route_solution(route_group_id)
    db.session.commit()
    return {"route_solution": route_solution.id}
