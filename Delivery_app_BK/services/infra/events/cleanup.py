"""Event cleanup and archival service for managing event table growth."""

from datetime import datetime, timedelta, timezone

from flask import current_app

from Delivery_app_BK.models import (
    AppEventOutbox,
    OrderEvent,
    RoutePlanEvent,
    db,
)


# Configuration for event retention
DEFAULT_EVENT_RETENTION_DAYS = 30
ARCHIVE_BATCH_SIZE = 1000


def cleanup_old_events(retention_days: int = DEFAULT_EVENT_RETENTION_DAYS) -> dict:
    """
    Archive/delete events older than retention period.
    
    Returns dict with cleanup statistics:
    {
        "order_events": 100,
        "delivery_plan_events": 50,
        "app_event_outbox": 10,
        "total_deleted": 160
    }
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    stats = {}
    
    event_models = [
        (OrderEvent, "order_events"),
        (RoutePlanEvent, "route_plan_events"),
        (AppEventOutbox, "app_event_outbox"),
    ]
    
    total_deleted = 0
    
    for model, label in event_models:
        try:
            deleted_count = db.session.query(model).filter(
                model.occurred_at < cutoff_date,
            ).delete(synchronize_session=False)
            
            db.session.commit()
            stats[label] = deleted_count
            total_deleted += deleted_count
            
            current_app.logger.info(
                "Cleaned up %d old %s (before %s)",
                deleted_count, label, cutoff_date.isoformat()
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(
                "Failed to cleanup %s: %s",
                label, str(exc), exc_info=True
            )
    
    stats["total_deleted"] = total_deleted
    current_app.logger.info(
        "Event cleanup completed: deleted %d total events older than %d days",
        total_deleted, retention_days
    )
    
    return stats


def get_event_table_stats() -> dict:
    """
    Get statistics about event tables.
    
    Returns:
    {
        "order_events": {"count": 1000, "oldest": "2025-01-01T00:00:00Z"},
        ...
    }
    """
    stats = {}
    event_models = [
        (OrderEvent, "order_events"),
        (RoutePlanEvent, "route_plan_events"),
        (AppEventOutbox, "app_event_outbox"),
    ]
    
    for model, label in event_models:
        try:
            count = db.session.query(model).count()
            oldest = db.session.query(model.occurred_at).order_by(
                model.occurred_at.asc()
            ).limit(1).scalar()
            
            stats[label] = {
                "count": count,
                "oldest": oldest.isoformat() if oldest else None,
            }
        except Exception as exc:
            current_app.logger.error(
                "Failed to get stats for %s: %s",
                label, str(exc), exc_info=True
            )
            stats[label] = {"error": str(exc)}
    
    return stats
