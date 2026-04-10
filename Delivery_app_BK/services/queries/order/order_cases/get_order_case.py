from Delivery_app_BK.models import OrderCase
from Delivery_app_BK.errors import NotFound

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from .serialize_order_cases import serialize_order_cases


def get_order_case(order_case_id: int, ctx: ServiceContext):
    found_case = get_instance(
        ctx=ctx,
        model=OrderCase,
        value=order_case_id,
    )

    if not found_case:
        raise NotFound(f"Order case with id: {order_case_id} does not exist.")

    serialized = serialize_order_cases(
        instances=[found_case],
        ctx=ctx,
    )

    return {
        "order_case": serialized[0] if isinstance(serialized, list) else serialized
    }
