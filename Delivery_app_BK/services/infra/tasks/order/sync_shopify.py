from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.costumer import (
    sync_order_costumer_to_shopify,
)


def sync_shopify(order_id: int) -> None:
    sync_order_costumer_to_shopify(order_id)
