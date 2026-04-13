from __future__ import annotations

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteSolution, User, db
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    ensure_single_selected_route_solution,
)
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_deleted_for_route_group


def delete_route_solution(ctx: ServiceContext):
    incoming_data = ctx.incoming_data or {}
    route_solution_id = incoming_data.get("route_solution_id")
    if not route_solution_id:
        raise ValidationFailed("route_solution_id is required.")

    route_solution = get_instance(ctx=ctx, model=RouteSolution, value=route_solution_id)
    route_group_id = route_solution.route_group_id
    solution_label = route_solution.label
    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    plan_label = route_plan.label if route_plan is not None else None
    team_id = route_solution.team_id
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
    db.session.delete(route_solution)
    db.session.flush()
    ensure_single_selected_route_solution(route_group_id)
    db.session.commit()
    emit_route_solution_deleted_for_route_group(
        team_id=team_id,
        route_group_id=route_group_id,
        route_solution_id=route_solution.id,
        payload={
            "label": solution_label,
            "plan_label": plan_label,
            "plan_type": resolve_route_plan_workflow_type(),
        },
        actor=actor,
    )
    return {"route_solution": route_solution.id}
