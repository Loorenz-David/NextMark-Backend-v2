from __future__ import annotations

from typing import Any

from Delivery_app_BK.models import RouteSolution, User, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import resolve_actual_timestamp
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.route_solutions import serialize_route_solutions
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery import (
    ActualTimeMarkRequest,
    parse_mark_actual_time_request,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_event
from Delivery_app_BK.services.infra.jobs import enqueue_job
from Delivery_app_BK.services.infra.jobs.tasks.analytics import compute_route_metrics_job
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_updated


def mark_route_solution_actual_end_time(
    ctx: ServiceContext,
    route_solution_id: int,
    request: ActualTimeMarkRequest | dict[str, Any] | None,
):
    parsed = (
        request
        if isinstance(request, ActualTimeMarkRequest)
        else parse_mark_actual_time_request(request)
    )

    route_solution: RouteSolution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=route_solution_id,
    )
    route_solution.actual_end_time = resolve_actual_timestamp(parsed.time)
    db.session.add(route_solution)
    db.session.commit()
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

    enqueue_job(
        queue_key="default",
        fn=compute_route_metrics_job,
        args=(route_solution.id,),
        description=f"analytics:route_metrics:{route_solution.id}",
    )

    # Emit real-time event
    create_route_solution_event(
        ctx=ctx,
        team_id=route_solution.team_id,
        route_solution_id=route_solution.id,
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
        payload={
            "actual_end_time": route_solution.actual_end_time.isoformat() if route_solution.actual_end_time else None,
        },
    )
    emit_route_solution_updated(route_solution, payload={
        "actual_end_time": route_solution.actual_end_time.isoformat() if route_solution.actual_end_time else None,
        "notification_change_hint": "times_updated",
    }, actor=actor)

    return {
        "route_solution": serialize_route_solutions([route_solution], ctx),
    }
