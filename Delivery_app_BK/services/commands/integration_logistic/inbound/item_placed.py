from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Item, Order, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.infra.audit import (
    new_audit_event_id,
    record_order_audit_changes,
)
from Delivery_app_BK.services.domain.order.audit import (
    diff_item_audit_values,
    snapshot_item_audit_values,
)
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

    ctx = ServiceContext(
        identity={"team_id": order.team_id, "active_team_id": order.team_id}
    )
    changes = []
    for item in items:
        audit_before = snapshot_item_audit_values(item)
        item.item_position = request.logistic_location.location
        changes.extend(
            diff_item_audit_values(audit_before, snapshot_item_audit_values(item), item)
        )

    edit_event = build_order_edited_event(order, changed_sections=["items"])
    edit_event["event_id"] = new_audit_event_id()
    record_order_audit_changes(
        ctx,
        order_id=order.id,
        team_id=order.team_id,
        event_id=edit_event["event_id"],
        changes=changes,
    )
    db.session.commit()
    emit_order_events(ctx, [edit_event])

    return {"updated_count": len(items)}
