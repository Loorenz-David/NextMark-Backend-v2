from typing import List

from Delivery_app_BK.models import Order
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils.return_mapper import map_return_values
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState


def _count_open_order_cases(order: Order) -> int:
    cases = getattr(order, "order_cases", None) or []
    return sum(1 for case in cases if case.state != OrderCaseState.RESOLVED.value)


def serialize_driver_order_command_delta(instances: List[Order], ctx: ServiceContext):
    unpacked_instances = [
        {
            "id": instance.id,
            "client_id": instance.client_id,
            "order_state_id": instance.order_state_id,
            "open_order_cases": _count_open_order_cases(instance),
        }
        for instance in instances
    ]

    return map_return_values(unpacked_instances, ctx, "order")
