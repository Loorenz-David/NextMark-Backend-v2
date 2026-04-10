from Delivery_app_BK.services.commands.order.update_order_route_plan_batch import (
    update_orders_route_plan_batch,
)
from Delivery_app_BK.services.context import ServiceContext


def assign_orders_to_plan_batch(
    ctx: ServiceContext,
    plan_id: int,
    destination_route_group_id: int | None = None,
) -> dict:
    return update_orders_route_plan_batch(
        ctx,
        plan_id,
        destination_route_group_id=destination_route_group_id,
    )
