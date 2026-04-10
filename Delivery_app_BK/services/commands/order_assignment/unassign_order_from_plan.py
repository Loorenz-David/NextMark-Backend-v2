from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    unassign_order_route_plan,
)
from Delivery_app_BK.services.context import ServiceContext


def unassign_order_from_plan(
    ctx: ServiceContext,
    order_id: int,
) -> dict:
    return unassign_order_route_plan(ctx, order_id)
