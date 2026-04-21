from __future__ import annotations

from Delivery_app_BK.models import User, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    ensure_route_solution_actual_start_time,
)
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import apply_plan_state
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.infra.jobs import enqueue_job

from ._helpers import resolve_driver_route_solution, resolve_driver_route_stop
from ._timing_helpers import (
    build_timing_result,
    can_record_route_timestamp,
    reject_outside_window,
    resolve_candidate_timestamp,
)
from ._timing_request import DriverObservedTimeRequest, parse_driver_observed_time_request
from .serializers import (
    serialize_driver_route_timing_command_delta,
    serialize_driver_stop_timing_command_delta,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import (
    create_route_solution_event,
    create_route_solution_stop_event,
)
from Delivery_app_BK.services.infra.jobs.tasks.analytics import compute_route_metrics_job
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
    BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
)
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_updated
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import emit_route_solution_stop_updated


def mark_driver_stop_actual_arrival_time(
    ctx: ServiceContext,
    stop_client_id: str,
    request: DriverObservedTimeRequest | dict | None,
):
    parsed = (
        request
        if isinstance(request, DriverObservedTimeRequest)
        else parse_driver_observed_time_request(request)
    )

    route_stop = resolve_driver_route_stop(ctx, stop_client_id)
    route_solution = resolve_driver_route_solution(ctx, route_stop.route_solution_id)
    candidate_time = resolve_candidate_timestamp(parsed.observed_time)
    stop_delta = serialize_driver_stop_timing_command_delta(route_stop)

    if route_stop.actual_arrival_time is not None:
        return build_timing_result(recorded=False, reason="already_recorded", stop=stop_delta)

    if not can_record_route_timestamp(route_solution, candidate_time):
        reject_outside_window(ctx, "Stop arrival was ignored because it is outside the route window.")
        return build_timing_result(recorded=False, reason="outside_route_window", stop=stop_delta)

    route_stop.actual_arrival_time = candidate_time
    route_start_backfilled = ensure_route_solution_actual_start_time(
        route_solution,
        candidate_time,
    )

    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    if route_start_backfilled and route_plan is not None:
        apply_plan_state(route_plan, PlanStateId.PROCESSING)

    db.session.add(route_stop)
    db.session.add(route_solution)
    db.session.commit()
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

    enqueue_job(
        queue_key="default",
        fn=compute_route_metrics_job,
        args=(route_solution.id,),
        description=f"analytics:route_metrics:{route_solution.id}",
    )

    create_route_solution_stop_event(
        ctx=ctx,
        team_id=route_solution.team_id,
        route_solution_stop_id=route_stop.id,
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
        payload={
            "actual_arrival_time": route_stop.actual_arrival_time.isoformat() if route_stop.actual_arrival_time else None,
        },
    )
    emit_route_solution_stop_updated(
        route_stop,
        payload={
            "actual_arrival_time": route_stop.actual_arrival_time.isoformat() if route_stop.actual_arrival_time else None,
        },
        actor=actor,
    )

    route_delta = None
    if route_start_backfilled:
        create_route_solution_event(
            ctx=ctx,
            team_id=route_solution.team_id,
            route_solution_id=route_solution.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
            payload={
                "actual_start_time": route_solution.actual_start_time.isoformat() if route_solution.actual_start_time else None,
            },
        )
        emit_route_solution_updated(
            route_solution,
            payload={
                "actual_start_time": route_solution.actual_start_time.isoformat() if route_solution.actual_start_time else None,
                "notification_change_hint": "times_updated",
            },
            actor=actor,
        )
        route_delta = serialize_driver_route_timing_command_delta(route_solution)

    return build_timing_result(
        recorded=True,
        route=route_delta,
        stop=serialize_driver_stop_timing_command_delta(route_stop),
    )
