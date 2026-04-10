from __future__ import annotations

from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import apply_plan_state
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId

from ._helpers import resolve_driver_route_solution
from ._timing_helpers import (
    build_timing_result,
    can_record_route_timestamp,
    reject_outside_window,
    resolve_candidate_timestamp,
)
from ._timing_request import DriverObservedTimeRequest, parse_driver_observed_time_request
from .serializers import serialize_driver_route_timing_command_delta


def mark_driver_route_actual_start_time(
    ctx: ServiceContext,
    route_id: int,
    request: DriverObservedTimeRequest | dict | None,
):  

    parsed = (
        request
        if isinstance(request, DriverObservedTimeRequest)
        else parse_driver_observed_time_request(request)
    )



    route_solution = resolve_driver_route_solution(ctx, route_id)
    candidate_time = resolve_candidate_timestamp(parsed.observed_time)
    route_delta = serialize_driver_route_timing_command_delta(route_solution)
   
    if route_solution.actual_start_time is not None:
        return build_timing_result(recorded=False, reason="already_recorded", route=route_delta)

    if not can_record_route_timestamp(route_solution, candidate_time):
        print('cannot record time ')
        reject_outside_window(ctx, "Route start was ignored because it is outside the route window.")
        return build_timing_result(recorded=False, reason="outside_route_window", route=route_delta)
  
    route_solution.actual_start_time = candidate_time

    # Transition the route plan to PROCESSING when the driver starts the route.
    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None
    if route_plan is not None:
        apply_plan_state(route_plan, PlanStateId.PROCESSING)

    db.session.add(route_solution)
    db.session.commit()

    return build_timing_result(
        recorded=True,
        route=serialize_driver_route_timing_command_delta(route_solution),
    )
