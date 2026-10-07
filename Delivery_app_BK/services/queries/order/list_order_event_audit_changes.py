from Delivery_app_BK.models import OrderAuditLog, db


def list_order_event_audit_changes(
    *,
    team_id: int,
    order_id: int,
    event_id: str,
) -> list[OrderAuditLog]:
    """Field-level changes recorded for one order event, in recording order."""
    return (
        db.session.query(OrderAuditLog)
        .filter(
            OrderAuditLog.team_id == team_id,
            OrderAuditLog.order_id == order_id,
            OrderAuditLog.event_id == event_id,
        )
        .order_by(OrderAuditLog.id.asc())
        .all()
    )
