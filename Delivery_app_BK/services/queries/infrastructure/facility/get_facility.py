from Delivery_app_BK.models import Facility
from Delivery_app_BK.errors import NotFound
from ....context import ServiceContext
from ...get_instance import get_instance
from .serialize_facilities import serialize_facilities


def get_facility(facility_id: int, ctx: ServiceContext):
    found_facility = get_instance(ctx=ctx, model=Facility, value=facility_id)
    if not found_facility:
        raise NotFound(f"Facility with id: {facility_id} does not exist.")
    serialized = serialize_facilities(instances=[found_facility], ctx=ctx)
    return {"facility": serialized[0] if isinstance(serialized, list) else serialized}
