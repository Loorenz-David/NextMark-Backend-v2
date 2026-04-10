from Delivery_app_BK.models import Order, db
from Delivery_app_BK.services.domain.order.shopify import should_fulfill_shopify_order
from Delivery_app_BK.services.infra.jobs import enqueue_job
from Delivery_app_BK.services.infra.tasks.order.fulfill_shopify_order import (
    fulfill_shopify_order,
)


def sync_shopify_fulfillment_on_order_completed(order_event) -> None:
    order = getattr(order_event, "order", None)
    if order is None:
        order = db.session.get(Order, getattr(order_event, "order_id", None))
    if order is None:
        return
    if not should_fulfill_shopify_order(order):
        return

    enqueue_job(
        queue_key="default",
        fn=fulfill_shopify_order,
        args=(order.id,),
        description=f"fulfill-shopify-order:{order.id}",
    )
