from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    update_order_route_plan,
)
from Delivery_app_BK.services.context import ServiceContext


def assign_order_to_plan(
    ctx: ServiceContext,
    order_id: int,
    plan_id: int,
    destination_route_group_id: int | None = None,
) -> dict:
    return update_order_route_plan(
        ctx,
        order_id,
        plan_id,
        destination_route_group_id=destination_route_group_id,
    )
