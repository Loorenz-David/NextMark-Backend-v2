from typing import Iterable, Mapping
from uuid import uuid4

from Delivery_app_BK.models import OrderAuditLog, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.audit import OrderFieldChange


def new_audit_event_id() -> str:
    return str(uuid4())


def record_order_audit_changes(
    ctx: ServiceContext,
    *,
    order_id: int | None,
    team_id: int | None,
    event_id: str,
    changes: Iterable[OrderFieldChange],
    attribute_to_user: bool = True,
) -> list[OrderAuditLog]:
    """Stage audit rows on the caller's session. The caller's commit persists
    them together with the edit they describe; this never commits.

    ``attribute_to_user=False`` is for changes the session only relayed, such
    as a customer's form submitted on a staff device."""
    if order_id is None:
        return []

    rows = [
        OrderAuditLog(
            order_id=order_id,
            team_id=team_id if team_id is not None else ctx.team_id,
            event_id=event_id,
            field_name=change.field_name,
            from_value=change.from_value,
            to_value=change.to_value,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            entity_label=change.entity_label,
            changed_by_user_id=(ctx.user_id or None) if attribute_to_user else None,
        )
        for change in changes
    ]
    if rows:
        db.session.add_all(rows)
    return rows


def record_order_audit_changes_by_order(
    ctx: ServiceContext,
    changes_by_order_id: Mapping[int, list[OrderFieldChange]],
) -> dict[int, str]:
    """Stage one audit batch per order and return the event id each order's
    edit event must carry so the rows attach to it."""
    event_id_by_order_id: dict[int, str] = {}
    for order_id, changes in changes_by_order_id.items():
        event_id = new_audit_event_id()
        record_order_audit_changes(
            ctx,
            order_id=order_id,
            team_id=None,
            event_id=event_id,
            changes=changes,
        )
        event_id_by_order_id[order_id] = event_id
    return event_id_by_order_id
