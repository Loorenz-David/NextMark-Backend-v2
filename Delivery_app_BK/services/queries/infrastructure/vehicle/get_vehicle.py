from Delivery_app_BK.models import Vehicle
from Delivery_app_BK.errors import NotFound

from ....context import ServiceContext
from ...get_instance import get_instance
from .serialize_vehicles import serialize_vehicles


def get_vehicle(vehicle_id: int, ctx: ServiceContext):
    found_vehicle = get_instance(
        ctx=ctx,
        model=Vehicle,
        value=vehicle_id,
    )

    if not found_vehicle:
        raise NotFound(f"Vehicle with id: {vehicle_id} does not exist.")

    serialized = serialize_vehicles(
        instances=[found_vehicle],
        ctx=ctx,
    )

    return {
        "vehicle": serialized[0] if isinstance(serialized, list) else serialized
    }
