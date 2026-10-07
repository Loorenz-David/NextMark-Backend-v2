from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteSolution, User, db

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.commands.utils import build_create_result
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_event
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    ensure_single_selected_route_solution,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.arrival_tracking import (
    collect_arrival_changes,
    snapshot_route_arrivals,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.infra.jobs import enqueue_job
from Delivery_app_BK.services.infra.jobs.tasks.analytics import compute_route_metrics_job
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_updated


def select_route_solution(ctx: ServiceContext, route_solution_id: int):
    route_solution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=route_solution_id,
    )
    route_group_id = getattr(route_solution, "route_group_id", None)
    if not route_group_id:
        raise ValidationFailed("Route solution has no route group.")

    arrival_snapshot = snapshot_route_arrivals(route_solution.team_id, [route_group_id])
    updated = ensure_single_selected_route_solution(
        route_group_id,
        preferred_route_solution_id=route_solution.id,
    )
    db.session.add_all(updated or [route_solution])
    db.session.commit()

    enqueue_job(
        queue_key="default",
        fn=compute_route_metrics_job,
        args=(route_solution.id,),
        description=f"analytics:route_metrics:{route_solution.id}",
    )

    # Emit real-time events
    team_id = route_solution.team_id
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
    arrival_outcome = collect_arrival_changes(arrival_snapshot, cause="variant_selected")

    for updated_route in updated or [route_solution]:
        create_route_solution_event(
            ctx=ctx,
            team_id=team_id,
            route_solution_id=updated_route.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
            payload={"is_selected": bool(updated_route.is_selected)},
        )
        # Every flipped variant refreshes; only the newly selected one notifies.
        is_newly_selected = updated_route.id == route_solution.id
        emit_route_solution_updated(
            updated_route,
            payload={
                "is_selected": bool(updated_route.is_selected),
                "notification_change_hint": "variant_selected",
                **(arrival_outcome.notification_payload if is_newly_selected else {}),
            },
            actor=actor,
            notify=is_newly_selected,
        )

    if arrival_outcome.events:
        emit_order_events(ctx, arrival_outcome.events)

    return {
        "route_solution": build_create_result(
            ctx,
            updated or [route_solution],
            extract_fields=["id", "is_selected"],
        ),
    }
