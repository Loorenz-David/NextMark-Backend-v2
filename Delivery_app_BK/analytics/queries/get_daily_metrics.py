"""Query: fetch AnalyticsDailyFact rows for a team."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def get_daily_metrics(
    team_id: int,
    days_back: int = 30,
    zone_id: Optional[int] = None,
) -> list:
    """Return AnalyticsDailyFact ORM rows for the given team.

    Args:
        team_id:  Scopes results to this team.
        days_back: How many days back from today to include (default: 30).
        zone_id:  None = global rows (zone_id IS NULL);
                  int = specific zone rows.

    Returns a list of AnalyticsDailyFact ORM instances ordered newest-first.
    """
    from Delivery_app_BK.models import db
    from Delivery_app_BK.models.tables.analytics.analytics_daily_fact import (
        AnalyticsDailyFact,
    )

    cutoff = date.today() - timedelta(days=days_back)
    q = db.session.query(AnalyticsDailyFact).filter(
        AnalyticsDailyFact.team_id == team_id,
        AnalyticsDailyFact.date >= cutoff,
        AnalyticsDailyFact.zone_id == zone_id,  # IS NULL when zone_id=None
    )
    return q.order_by(AnalyticsDailyFact.date.desc()).all()
