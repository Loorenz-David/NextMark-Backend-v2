from Delivery_app_BK.models import RouteSolutionStop


def serialize_driver_stop_timing_command_delta(instance: RouteSolutionStop):
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "actual_arrival_time": instance.actual_arrival_time.isoformat() if instance.actual_arrival_time else None,
        "actual_departure_time": instance.actual_departure_time.isoformat() if instance.actual_departure_time else None,
    }
