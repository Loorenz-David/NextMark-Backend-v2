from __future__ import annotations

from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext

from ._helpers import resolve_driver_route_solution, resolve_driver_route_stop
from ._timing_helpers import (
    build_timing_result,
    can_record_route_timestamp,
    reject_outside_window,
    resolve_candidate_timestamp,
)
from ._timing_request import DriverObservedTimeRequest, parse_driver_observed_time_request
from .serializers import serialize_driver_stop_timing_command_delta


def mark_driver_stop_actual_departure_time(
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

    if route_stop.actual_departure_time is not None:
        return build_timing_result(recorded=False, reason="already_recorded", stop=stop_delta)

    if not can_record_route_timestamp(route_solution, candidate_time):
        reject_outside_window(ctx, "Stop departure was ignored because it is outside the route window.")
        return build_timing_result(recorded=False, reason="outside_route_window", stop=stop_delta)

    route_stop.actual_departure_time = candidate_time
    db.session.add(route_stop)
    db.session.commit()

    return build_timing_result(
        recorded=True,
        stop=serialize_driver_stop_timing_command_delta(route_stop),
    )
