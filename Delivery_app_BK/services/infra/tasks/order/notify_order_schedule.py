from Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order import (
    notify_order_schedule as notify_order_schedule_command,
)


def notify_order_schedule(target_id: int, order_id: int, scheduled_date: str) -> None:
    notify_order_schedule_command(target_id, order_id, scheduled_date)
