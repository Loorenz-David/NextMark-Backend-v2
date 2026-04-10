"""Route-level analytics aggregator.

Reads a completed/selected RouteSolution, computes per-stop delay metrics,
and upserts a RouteMetricsSnapshot row.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.analytics.route_metrics_snapshot import (
    RouteMetricsSnapshot as RouteMetricsSnapshotModel,
)
from Delivery_app_BK.analytics.domain.route_metrics import RouteMetricsSnapshot
from Delivery_app_BK.analytics.zone_attribution import derive_route_zone

# Stops within this many seconds of expected arrival are considered on-time
_ON_TIME_TOLERANCE_SECONDS = 300  # 5 minutes


def compute_route_metrics(route_solution_id: int) -> Optional[RouteMetricsSnapshot]:
    """Compute a RouteMetricsSnapshot domain object for the given route.

    Returns None if the route cannot be found.
    """
    from Delivery_app_BK.models import RouteSolution

    route = db.session.get(RouteSolution, route_solution_id)
    if route is None:
        return None

    stops = route.stops or []
    measured_stops = [s for s in stops if s.actual_arrival_time and s.expected_arrival_time]

    total_stops = len(stops)
    on_time_stops = 0
    early_stops = 0
    late_stops = 0
    delay_values: list[float] = []

    for stop in measured_stops:
        delay_s = (
            stop.actual_arrival_time - stop.expected_arrival_time
        ).total_seconds()
        delay_values.append(delay_s)

        if abs(delay_s) <= _ON_TIME_TOLERANCE_SECONDS:
            on_time_stops += 1
        elif delay_s < 0:
            early_stops += 1
        else:
            late_stops += 1

    avg_delay = sum(delay_values) / len(delay_values) if delay_values else 0.0
    max_delay = max(delay_values, default=0.0)
    on_time_rate = on_time_stops / total_stops if total_stops else 0.0
    delay_rate = late_stops / total_stops if total_stops else 0.0

    total_service_time = sum(
        (s.expected_service_duration_seconds or 0) for s in stops
    )

    zone_id, zone_version_id = derive_route_zone(route)

    return RouteMetricsSnapshot(
        route_solution_id=route_solution_id,
        team_id=route.team_id,
        expected_start_time=route.expected_start_time,
        total_stops=total_stops,
        on_time_stops=on_time_stops,
        early_stops=early_stops,
        late_stops=late_stops,
        avg_delay_seconds=avg_delay,
        max_delay_seconds=max_delay,
        on_time_rate=on_time_rate,
        delay_rate=delay_rate,
        total_distance_meters=float(route.total_distance_meters or 0),
        total_travel_time_seconds=float(route.total_travel_time_seconds or 0),
        total_service_time_seconds=float(total_service_time),
        total_orders=len(stops),
        zone_id=zone_id,
        zone_version_id=zone_version_id,
        computed_at=datetime.now(timezone.utc),
    )


def persist_route_metrics(snapshot: RouteMetricsSnapshot) -> RouteMetricsSnapshotModel:
    """Upsert a RouteMetricsSnapshot into the database.

    Always overwrites the existing row — never skip, so zone_id updates
    from Phase 4 backfills propagate cleanly.
    """
    row = (
        db.session.query(RouteMetricsSnapshotModel)
        .filter_by(route_solution_id=snapshot.route_solution_id)
        .first()
    )

    if row is None:
        row = RouteMetricsSnapshotModel(route_solution_id=snapshot.route_solution_id)
        db.session.add(row)

    row.team_id = snapshot.team_id
    row.expected_start_time = snapshot.expected_start_time
    row.computed_at = snapshot.computed_at or datetime.now(timezone.utc)
    row.total_stops = snapshot.total_stops
    row.on_time_stops = snapshot.on_time_stops
    row.early_stops = snapshot.early_stops
    row.late_stops = snapshot.late_stops
    row.avg_delay_seconds = snapshot.avg_delay_seconds
    row.max_delay_seconds = snapshot.max_delay_seconds
    row.on_time_rate = snapshot.on_time_rate
    row.delay_rate = snapshot.delay_rate
    row.total_distance_meters = snapshot.total_distance_meters
    row.total_travel_time_seconds = snapshot.total_travel_time_seconds
    row.total_service_time_seconds = snapshot.total_service_time_seconds
    row.total_orders = snapshot.total_orders
    row.zone_id = snapshot.zone_id
    row.zone_version_id = snapshot.zone_version_id

    db.session.commit()
    return row
