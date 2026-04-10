from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP

from .normalizers import normalize_time_value


def apply_route_solution_field_updates(
    route_solution: RouteSolution,
    updates: dict,
) -> tuple[bool, bool, bool]:
    has_start_location = "start_location" in updates
    has_end_location = "end_location" in updates
    has_set_start = "set_start_time" in updates
    has_set_end = "set_end_time" in updates
    has_eta_tolerance_seconds = "eta_tolerance_seconds" in updates
    has_eta_message_tolerance = "eta_message_tolerance" in updates
    has_driver = "driver_id" in updates
    has_vehicle = "vehicle_id" in updates
    has_route_end_strategy = "route_end_strategy" in updates
    has_stops_service_time = "stops_service_time" in updates

    start_location = updates.get("start_location")
    end_location = updates.get("end_location")

    set_start_time = normalize_time_value(updates.get("set_start_time"))
    set_end_time = normalize_time_value(updates.get("set_end_time"))
    eta_tolerance_seconds = updates.get("eta_tolerance_seconds", route_solution.eta_tolerance_seconds)
    eta_message_tolerance = updates.get(
        "eta_message_tolerance",
        route_solution.eta_message_tolerance,
    )
    driver_id = updates.get("driver_id")
    vehicle_id = updates.get("vehicle_id")
    route_end_strategy = updates.get("route_end_strategy")
    stops_service_time = updates.get("stops_service_time")

    has_address_change = False
    if has_start_location and start_location != route_solution.start_location:
        route_solution.start_location = start_location
        has_address_change = True
    if has_end_location and end_location != route_solution.end_location:
        route_solution.end_location = end_location
        has_address_change = True
    if has_route_end_strategy:
        if route_end_strategy == ROUND_TRIP and start_location != end_location:
            route_solution.end_location = route_solution.start_location
            has_address_change = True
        route_solution.route_end_strategy = route_end_strategy

    has_time_change = False
    if has_set_start and set_start_time != route_solution.set_start_time:
        route_solution.set_start_time = set_start_time
        has_time_change = True
    if has_set_end and set_end_time != route_solution.set_end_time:
        route_solution.set_end_time = set_end_time
        has_time_change = True
    if has_eta_tolerance_seconds and eta_tolerance_seconds != route_solution.eta_tolerance_seconds:
        route_solution.eta_tolerance_seconds = eta_tolerance_seconds
        has_time_change = True
    if has_eta_message_tolerance and eta_message_tolerance != route_solution.eta_message_tolerance:
        route_solution.eta_message_tolerance = eta_message_tolerance
        has_time_change = True

    if has_driver:
        route_solution.driver_id = driver_id

    if has_vehicle:
        route_solution.vehicle_id = vehicle_id

    has_service_time_change = False
    if has_stops_service_time and stops_service_time != route_solution.stops_service_time:
        route_solution.stops_service_time = stops_service_time
        has_service_time_change = True

    return has_address_change, has_time_change, has_service_time_change
