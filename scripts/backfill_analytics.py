"""Backfill analytics snapshots and daily facts.

Usage:
    python scripts/backfill_analytics.py --days-back 90
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from Delivery_app_BK import create_app
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.team.team import Team
from Delivery_app_BK.models.tables.delivery_plan.delivery_plan_types.local_delivery_plan.route_solutions.route_solution import (
    RouteSolution,
)
from Delivery_app_BK.analytics.aggregators.route_aggregator import (
    compute_route_metrics,
    persist_route_metrics,
)
from Delivery_app_BK.analytics.aggregators.daily_aggregator import (
    aggregate_daily_metrics,
    persist_daily_metrics,
)


def backfill_route_metrics(days_back: int = 90) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    routes = (
        db.session.query(RouteSolution)
        .filter(
            RouteSolution.expected_start_time >= cutoff,
            RouteSolution.is_selected.is_(True),
        )
        .all()
    )

    processed = 0
    for route in routes:
        snapshot = compute_route_metrics(route.id)
        if snapshot is None:
            continue
        persist_route_metrics(snapshot)
        processed += 1

    return processed


def backfill_daily_metrics(days_back: int = 90) -> int:
    teams = db.session.query(Team).all()
    today_utc = datetime.now(timezone.utc).date()

    written = 0
    for offset in range(days_back):
        target_date = today_utc - timedelta(days=offset + 1)
        for team in teams:
            team_tz = team.time_zone or "UTC"
            metrics = aggregate_daily_metrics(
                team_id=team.id,
                target_date=target_date,
                team_timezone=team_tz,
                zone_id=None,
            )
            persist_daily_metrics(metrics)
            written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill analytics data")
    parser.add_argument("--days-back", type=int, default=90)
    parser.add_argument("--env", type=str, default="development")
    args = parser.parse_args()

    app = create_app(args.env)
    with app.app_context():
        route_rows = backfill_route_metrics(days_back=args.days_back)
        daily_rows = backfill_daily_metrics(days_back=args.days_back)
        print(
            {
                "status": "ok",
                "days_back": args.days_back,
                "route_snapshots_processed": route_rows,
                "daily_fact_rows_written": daily_rows,
            }
        )


if __name__ == "__main__":
    main()
