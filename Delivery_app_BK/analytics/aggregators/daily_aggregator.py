"""Daily analytics aggregator.

Aggregates order and route metrics for a given (team, date, zone_id) tuple
into an AnalyticsDailyFact row.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.analytics.analytics_daily_fact import (
    AnalyticsDailyFact as AnalyticsDailyFactModel,
)
from Delivery_app_BK.models.tables.analytics.route_metrics_snapshot import (
    RouteMetricsSnapshot as RouteMetricsSnapshotModel,
)
from Delivery_app_BK.analytics.domain.daily_metrics import AnalyticsDailyFact
from Delivery_app_BK.services.domain.order.order_states import OrderStateId


def _team_day_window_utc(
    target_date: date, team_timezone: str
) -> tuple[datetime, datetime]:
    """Return UTC (start, end) for a team's local calendar day.

    Falls back to UTC if the team's IANA timezone cannot be resolved.
    """
    try:
        tz = ZoneInfo(team_timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    local_start = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=tz
    )
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def aggregate_daily_metrics(
    team_id: int,
    target_date: date,
    team_timezone: str = "UTC",
    zone_id: Optional[int] = None,
    zone_version_id: Optional[int] = None,
) -> AnalyticsDailyFact:
    """Compute daily aggregate metrics for a team on a given local date.

    zone_id=None → global (team-wide) aggregate.
    zone_id=<int> → per-zone aggregate (active once zone attribution populates zone data).
    """
    from Delivery_app_BK.models.tables.order.order import Order
    from Delivery_app_BK.models import RouteSolution

    utc_start, utc_end = _team_day_window_utc(target_date, team_timezone)

    # ── Order metrics ─────────────────────────────────────────────────────────
    orders_q = db.session.query(Order).filter(
        Order.team_id == team_id,
        Order.creation_date >= utc_start,
        Order.creation_date < utc_end,
    )
    all_orders = orders_q.all()

    total_orders_created = len(all_orders)
    total_orders_completed = sum(
        1 for o in all_orders if o.order_state_id == OrderStateId.COMPLETED
    )
    total_orders_failed = sum(
        1 for o in all_orders if o.order_state_id == OrderStateId.FAIL
    )
    scheduled_orders = sum(
        1 for o in all_orders if getattr(o, "route_plan_id", None) is not None
    )
    unscheduled_orders = total_orders_created - scheduled_orders
    completion_rate = (
        total_orders_completed / total_orders_created if total_orders_created else 0.0
    )

    # ── Route metrics ───────────────────────────────────────────────────────
    routes_q = db.session.query(RouteSolution).filter(
        RouteSolution.team_id == team_id,
        RouteSolution.is_selected.is_(True),
        RouteSolution.expected_start_time >= utc_start,
        RouteSolution.expected_start_time < utc_end,
    )
    routes = routes_q.all()
    route_ids = [r.id for r in routes]

    total_routes = len(routes)
    routes_completed = sum(1 for r in routes if r.actual_end_time is not None)
    routes_active = total_routes - routes_completed

    # Pull aggregated snapshot metrics for these routes
    snapshots: list[RouteMetricsSnapshotModel] = []
    if route_ids:
        snap_q = db.session.query(RouteMetricsSnapshotModel).filter(
            RouteMetricsSnapshotModel.route_solution_id.in_(route_ids)
        )
        if zone_id is not None:
            snap_q = snap_q.filter(RouteMetricsSnapshotModel.zone_id == zone_id)
        if zone_version_id is not None:
            snap_q = snap_q.filter(
                RouteMetricsSnapshotModel.zone_version_id == zone_version_id
            )
        snapshots = snap_q.all()

    avg_delay = (
        sum(s.avg_delay_seconds for s in snapshots) / len(snapshots)
        if snapshots else 0.0
    )
    late_routes_count = sum(1 for s in snapshots if s.delay_rate > 0)
    on_time_routes_count = sum(1 for s in snapshots if s.delay_rate == 0)
    total_distance = sum(s.total_distance_meters for s in snapshots)
    total_travel_time = sum(s.total_travel_time_seconds for s in snapshots)

    return AnalyticsDailyFact(
        team_id=team_id,
        date=target_date,
        total_orders_created=total_orders_created,
        total_orders_completed=total_orders_completed,
        total_orders_failed=total_orders_failed,
        scheduled_orders=scheduled_orders,
        unscheduled_orders=unscheduled_orders,
        completion_rate=completion_rate,
        total_routes=total_routes,
        routes_completed=routes_completed,
        routes_active=routes_active,
        avg_delay_seconds=avg_delay,
        late_routes_count=late_routes_count,
        on_time_routes_count=on_time_routes_count,
        total_distance_meters=total_distance,
        total_travel_time_seconds=total_travel_time,
        zone_id=zone_id,
        zone_version_id=zone_version_id,
    )


def persist_daily_metrics(metrics: AnalyticsDailyFact) -> AnalyticsDailyFactModel:
    """Upsert an AnalyticsDailyFact row identified by (team_id, date, zone_id).

    SQLAlchemy generates `WHERE zone_id IS NULL` correctly when zone_id=None,
    matching the partial unique index behaviour in PostgreSQL.
    """
    row = (
        db.session.query(AnalyticsDailyFactModel)
        .filter_by(team_id=metrics.team_id, date=metrics.date, zone_id=metrics.zone_id)
        .first()
    )

    if row is None:
        row = AnalyticsDailyFactModel(
            team_id=metrics.team_id,
            date=metrics.date,
            zone_id=metrics.zone_id,
        )
        db.session.add(row)

    row.total_orders_created = metrics.total_orders_created
    row.total_orders_completed = metrics.total_orders_completed
    row.total_orders_failed = metrics.total_orders_failed
    row.scheduled_orders = metrics.scheduled_orders
    row.unscheduled_orders = metrics.unscheduled_orders
    row.completion_rate = metrics.completion_rate
    row.total_routes = metrics.total_routes
    row.routes_completed = metrics.routes_completed
    row.routes_active = metrics.routes_active
    row.avg_delay_seconds = metrics.avg_delay_seconds
    row.late_routes_count = metrics.late_routes_count
    row.on_time_routes_count = metrics.on_time_routes_count
    row.total_distance_meters = metrics.total_distance_meters
    row.total_travel_time_seconds = metrics.total_travel_time_seconds
    row.zone_version_id = metrics.zone_version_id

    db.session.commit()
    return row
