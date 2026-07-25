import logging

from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.costumer import (
    sync_order_costumer_to_shopify,
)


logger = logging.getLogger(__name__)


def sync_shopify(order_id: int) -> None:
    logger.info("[shopify-costumer-sync] task start order_id=%s", order_id)
    try:
        sync_order_costumer_to_shopify(order_id)
    except Exception:
        logger.exception("[shopify-costumer-sync] task failed order_id=%s", order_id)
        raise
    logger.info("[shopify-costumer-sync] task done order_id=%s", order_id)
