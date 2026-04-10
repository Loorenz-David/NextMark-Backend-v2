from Delivery_app_BK.models import RouteSolution


def serialize_driver_route_timing_command_delta(instance: RouteSolution):
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "actual_start_time": instance.actual_start_time.isoformat() if instance.actual_start_time else None,
        "actual_end_time": instance.actual_end_time.isoformat() if instance.actual_end_time else None,
    }
