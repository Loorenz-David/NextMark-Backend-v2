from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order import (
    fulfill_shopify_order as fulfill_shopify_order_command,
)


def fulfill_shopify_order(order_id: int) -> None:
    fulfill_shopify_order_command(order_id)
