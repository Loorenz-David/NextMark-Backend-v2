from Delivery_app_BK.models import RouteSolution, RouteSolutionStop


def serialize_route_solution_short(route_solution: RouteSolution) -> dict:
    return {

        "client_id": route_solution.client_id,
        "label":route_solution.label,
        "is_optimized": route_solution.is_optimized,
        "eta_message_tolerance": route_solution.eta_message_tolerance if route_solution.eta_message_tolerance is not None else 1800,
        "start_leg_polyline": route_solution.start_leg_polyline,
        "end_leg_polyline": route_solution.end_leg_polyline,
        "_representation": "summary",

    }


def serialize_stop_short(stop: RouteSolutionStop) -> dict:
    return {
        "id": stop.id,
        "client_id": stop.client_id,
        "stop_order": stop.stop_order,
    }
