from Delivery_app_BK.route_optimization.constants.route_end_strategy import (
    CUSTOM_END_ADDRESS,
    LAST_STOP,
    ROUND_TRIP,
)

from .route_times import combine_plan_date_and_local_hhmm_to_utc, resolve_request_timezone
from .service_time import normalize_service_time_payload


def normalize_local_delivery_route_solution_defaults(
    ctx,
    plan_instance,
    local_delivery_defaults: dict | None,
) -> dict:
    defaults = local_delivery_defaults if isinstance(local_delivery_defaults, dict) else {}
    route_solution_defaults = defaults.get("route_solution")
    if not isinstance(route_solution_defaults, dict):
        route_solution_defaults = {}

    raw_strategy = route_solution_defaults.get("route_end_strategy")
    allowed_strategies = {ROUND_TRIP, CUSTOM_END_ADDRESS, LAST_STOP}
    route_end_strategy = (
        raw_strategy
        if isinstance(raw_strategy, str) and raw_strategy in allowed_strategies
        else ROUND_TRIP
    )

    set_start_time = route_solution_defaults.get("set_start_time")
    if not isinstance(set_start_time, str):
        set_start_time = None

    set_end_time = route_solution_defaults.get("set_end_time")
    if not isinstance(set_end_time, str):
        set_end_time = None

    start_location = route_solution_defaults.get("start_location")
    if not isinstance(start_location, dict):
        start_location = None

    end_location = route_solution_defaults.get("end_location")
    if not isinstance(end_location, dict):
        end_location = None

    request_timezone = resolve_request_timezone(ctx, plan_instance)
    expected_start_time = combine_plan_date_and_local_hhmm_to_utc(
        plan_date=plan_instance.start_date,
        hhmm=set_start_time,
        tz=request_timezone,
    )

    driver_id = route_solution_defaults.get("driver_id")
    if not isinstance(driver_id, int) or isinstance(driver_id, bool):
        driver_id = None

    start_facility_id = route_solution_defaults.get("start_facility_id")
    if not isinstance(start_facility_id, int) or isinstance(start_facility_id, bool):
        start_facility_id = None

    eta_tolerance_seconds = route_solution_defaults.get("eta_tolerance_seconds")
    if not isinstance(eta_tolerance_seconds, int) or isinstance(eta_tolerance_seconds, bool):
        eta_tolerance_seconds = 0

    eta_message_tolerance = route_solution_defaults.get("eta_message_tolerance")
    if not isinstance(eta_message_tolerance, int) or isinstance(eta_message_tolerance, bool):
        eta_message_tolerance = 1800

    return {
        "start_location": start_location,
        "end_location": end_location,
        "set_start_time": set_start_time,
        "expected_start_time": expected_start_time,
        "set_end_time": set_end_time,
        "route_end_strategy": route_end_strategy,
        "driver_id": driver_id,
        "start_facility_id": start_facility_id,
        "eta_tolerance_seconds": max(0, min(7200, eta_tolerance_seconds)),
        "eta_message_tolerance": max(0, min(7200, eta_message_tolerance)),
        "stops_service_time": normalize_service_time_payload(
            route_solution_defaults.get("stops_service_time")
        ),
    }
