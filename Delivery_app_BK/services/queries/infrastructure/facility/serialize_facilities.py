from typing import List
from Delivery_app_BK.models import Facility
from ....context import ServiceContext
from ...utils import map_return_values


def serialize_facilities(instances: List[Facility], ctx: ServiceContext):
    unpacked_instances = []
    for instance in instances:
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "name": instance.name,
            "property_location": instance.property_location,
            "facility_type": instance.facility_type,
            "can_dispatch": instance.can_dispatch,
            "can_receive_returns": instance.can_receive_returns,
            "operating_hours": instance.operating_hours,
            "default_loading_time_seconds": instance.default_loading_time_seconds,
            "default_unloading_time_seconds": instance.default_unloading_time_seconds,
            "max_orders_per_day": instance.max_orders_per_day,
            "external_refs": instance.external_refs,
            "team_id": instance.team_id,
        }
        unpacked_instances.append(unpacked)
    return map_return_values(unpacked_instances, ctx, "facility")
