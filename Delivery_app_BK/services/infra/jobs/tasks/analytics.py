"""Analytics background job tasks.

compute_route_metrics_job   — triggered after each route completes/is selected
aggregate_daily_metrics_job — triggered daily at ~00:05 UTC by the scheduler
"""
from __future__ import annotations

from datetime import date, timedelta, timezone, datetime

from Delivery_app_BK.services.infra.jobs import with_app_context


@with_app_context
def compute_route_metrics_job(route_solution_id: int) -> None:
    """Compute and persist route-level analytics for a single RouteSolution."""
    from Delivery_app_BK.analytics.aggregators.route_aggregator import (
        compute_route_metrics,
        persist_route_metrics,
    )

    snapshot = compute_route_metrics(route_solution_id)
    if snapshot is None:
        return
    persist_route_metrics(snapshot)


@with_app_context
def aggregate_daily_metrics_job() -> None:
    """Aggregate daily metrics for all active teams for yesterday (local time).

    Runs once per day. Computes:
      1. A global row per team (zone_id=None).
      2. Per-zone rows for any zone_ids already present in route snapshots
         (no-op until Phase 4 populates zone_id — the distinct query returns
         no rows, so the loop body never executes).
    """
    from Delivery_app_BK.models import db
    from Delivery_app_BK.models.tables.team.team import Team
    from Delivery_app_BK.models.tables.analytics.route_metrics_snapshot import (
        RouteMetricsSnapshot as RouteMetricsSnapshotModel,
    )
    from Delivery_app_BK.analytics.aggregators.daily_aggregator import (
        aggregate_daily_metrics,
        persist_daily_metrics,
    )

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    teams = db.session.query(Team).all()
    for team in teams:
        team_tz = team.time_zone or "UTC"

        # Global row (zone_id=None) — always computed
        global_metrics = aggregate_daily_metrics(
            team_id=team.id,
            target_date=yesterday,
            team_timezone=team_tz,
            zone_id=None,
        )
        persist_daily_metrics(global_metrics)

        # Per-zone rows — query distinct (zone_id, zone_version_id) pairs so
        # both dimensions flow into the daily fact and populate the composite
        # index (team_id, date, zone_version_id, zone_id).
        distinct_zone_pairs = (
            db.session.query(
                RouteMetricsSnapshotModel.zone_id,
                RouteMetricsSnapshotModel.zone_version_id,
            )
            .filter(
                RouteMetricsSnapshotModel.team_id == team.id,
                RouteMetricsSnapshotModel.zone_id.isnot(None),
            )
            .distinct()
            .all()
        )
        for zid, zvid in distinct_zone_pairs:
            zone_metrics = aggregate_daily_metrics(
                team_id=team.id,
                target_date=yesterday,
                team_timezone=team_tz,
                zone_id=zid,
                zone_version_id=zvid,
            )
            persist_daily_metrics(zone_metrics)
