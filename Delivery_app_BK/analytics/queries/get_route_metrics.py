"""Query: fetch RouteMetricsSnapshot rows for a team."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def get_route_metrics(
    team_id: int,
    days_back: int = 7,
    zone_id: Optional[int] = None,
) -> list:
    """Return RouteMetricsSnapshot ORM rows for the given team.

    Args:
        team_id:  Scopes results to this team.
        days_back: How many days back from now to include (default: 7).
        zone_id:  None = all zones; int = specific zone only.

    Returns a list of RouteMetricsSnapshot ORM instances ordered newest-first.
    """
    from Delivery_app_BK.models import db
    from Delivery_app_BK.models.tables.analytics.route_metrics_snapshot import (
        RouteMetricsSnapshot,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    q = db.session.query(RouteMetricsSnapshot).filter(
        RouteMetricsSnapshot.team_id == team_id,
        RouteMetricsSnapshot.created_at >= cutoff,
    )
    if zone_id is not None:
        q = q.filter(RouteMetricsSnapshot.zone_id == zone_id)

    return q.order_by(RouteMetricsSnapshot.created_at.desc()).all()
