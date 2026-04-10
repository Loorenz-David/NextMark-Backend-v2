from Delivery_app_BK.services.commands.order.update_order_route_plan_batch import (
    resolve_orders_selection as resolve_orders_selection_service,
)
from Delivery_app_BK.services.context import ServiceContext


def resolve_orders_selection(ctx: ServiceContext) -> dict:
    return resolve_orders_selection_service(ctx)
