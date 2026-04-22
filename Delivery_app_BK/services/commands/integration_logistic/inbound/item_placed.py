from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Item, Order, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import (
    ItemPlacedRequest,
)

def item_placed(request: ItemPlacedRequest) -> dict:
    order: Order | None = (
        db.session.query(Order)
        .filter(
            Order.external_order_id == request.order_id,
        )
        .first()
    )
    if order is None:
        raise NotFound(f"Order not found for orderId: {request.order_id!r}")

    items: list[Item] = (
        db.session.query(Item)
        .filter(
            Item.order_id == order.id,
            Item.article_number == request.item_sku,
        )
        .all()
    )
    if not items:
        return {
            "updated_count": 0,
            "warning": (
                f"No items found for SKU {request.item_sku!r} in order {request.order_id!r}"
            ),
        }

    for item in items:
        item.item_position = request.logistic_location.location

    db.session.commit()
    ctx = ServiceContext(
        identity={"team_id": order.team_id, "active_team_id": order.team_id}
    )
    emit_order_events(ctx, [build_order_edited_event(order, changed_sections=["items"])])

    return {"updated_count": len(items)}
