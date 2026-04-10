from __future__ import annotations

from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext

from ._helpers import resolve_driver_route_solution
from ._route_end_source import ROUTE_END_SOURCE_MANUAL
from ._timing_helpers import (
    build_timing_result,
    can_record_route_timestamp,
    mark_route_end_time,
    reject_outside_window,
    resolve_candidate_timestamp,
)
from ._timing_request import DriverObservedTimeRequest, parse_driver_observed_time_request
from .serializers import serialize_driver_route_timing_command_delta


def mark_driver_route_actual_end_time_manual(
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

    if not can_record_route_timestamp(route_solution, candidate_time):
        reject_outside_window(ctx, "Manual route end was ignored because it is outside the route window.")
        return build_timing_result(recorded=False, reason="outside_route_window", route=route_delta)

    recorded, reason = mark_route_end_time(
        route_solution,
        candidate_time=candidate_time,
        source=ROUTE_END_SOURCE_MANUAL,
    )
    if not recorded:
        return build_timing_result(recorded=False, reason=reason, route=route_delta)

    db.session.add(route_solution)
    db.session.commit()

    return build_timing_result(
        recorded=True,
        route=serialize_driver_route_timing_command_delta(route_solution),
    )
