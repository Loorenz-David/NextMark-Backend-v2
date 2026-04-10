from __future__ import annotations

from typing import Any

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    ensure_route_solution_actual_start_time,
    resolve_actual_timestamp,
)
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.queries.route_solutions import (
    serialize_route_solution_stops,
    serialize_route_solutions,
)
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery import (
    ActualTimeMarkRequest,
    parse_mark_actual_time_request,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.event_helpers import create_route_solution_stop_event
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import emit_route_solution_stop_updated


def mark_route_stop_actual_departure_time(
    ctx: ServiceContext,
    route_stop_id: int,
    request: ActualTimeMarkRequest | dict[str, Any] | None,
):
    parsed = (
        request
        if isinstance(request, ActualTimeMarkRequest)
        else parse_mark_actual_time_request(request)
    )

    route_stop: RouteSolutionStop = get_instance(
        ctx=ctx,
        model=RouteSolutionStop,
        value=route_stop_id,
    )
    route_solution: RouteSolution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=route_stop.route_solution_id,
    )
    timestamp = resolve_actual_timestamp(parsed.time)
    route_stop.actual_departure_time = timestamp
    route_start_backfilled = ensure_route_solution_actual_start_time(
        route_solution,
        timestamp,
    )

    db.session.add(route_stop)
    db.session.add(route_solution)
    db.session.commit()

    # Emit real-time event
    create_route_solution_stop_event(
        ctx=ctx,
        team_id=route_solution.team_id,
        route_solution_stop_id=route_stop.id,
        event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
        payload={
            "actual_departure_time": route_stop.actual_departure_time.isoformat() if route_stop.actual_departure_time else None,
        },
    )
    emit_route_solution_stop_updated(route_stop, payload={
        "actual_departure_time": route_stop.actual_departure_time.isoformat() if route_stop.actual_departure_time else None,
    })

    response = {
        "route_solution_stop": serialize_route_solution_stops([route_stop], ctx),
    }
    if route_start_backfilled:
        response["route_solution"] = serialize_route_solutions([route_solution], ctx)
    return response
