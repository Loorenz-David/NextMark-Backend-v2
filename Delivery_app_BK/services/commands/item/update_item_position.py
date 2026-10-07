from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import db, Item
from ...context import ServiceContext
from Delivery_app_BK.services.domain.order.audit import (
    diff_item_audit_values,
    snapshot_item_audit_values,
)
from Delivery_app_BK.services.infra.audit import (
    new_audit_event_id,
    record_order_audit_changes,
)
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from ...queries.get_instance import get_instance


def update_item_position(
    ctx: ServiceContext,
    item_id: int | str,
    position_name: str,
):
    try:
        item_instance: Item = get_instance(ctx, Item, item_id)
    except NoResultFound as exc:
        raise NotFound(str(exc)) from exc

    audit_before = snapshot_item_audit_values(item_instance)
    item_instance.item_position = position_name
    edit_event = _stage_item_edit_audit(ctx, item_instance, audit_before)
    db.session.commit()
    if edit_event is not None:
        emit_order_events(ctx, [edit_event])
    return item_instance


def _stage_item_edit_audit(
    ctx: ServiceContext,
    item_instance: Item,
    audit_before: dict,
) -> dict | None:
    order = item_instance.order
    changes = diff_item_audit_values(
        audit_before,
        snapshot_item_audit_values(item_instance),
        item_instance,
    )
    if order is None or not changes:
        return None

    edit_event = build_order_edited_event(order, changed_sections=["items"])
    edit_event["event_id"] = new_audit_event_id()
    record_order_audit_changes(
        ctx,
        order_id=order.id,
        team_id=order.team_id,
        event_id=edit_event["event_id"],
        changes=changes,
    )
    return edit_event
