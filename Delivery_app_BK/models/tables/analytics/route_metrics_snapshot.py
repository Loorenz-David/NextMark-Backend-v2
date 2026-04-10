"""ORM model for per-route analytics metrics snapshot."""
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Index, Integer, String, BigInteger
from sqlalchemy import ForeignKey

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class RouteMetricsSnapshot(db.Model):
    """One row per RouteSolution, capturing computed performance metrics.

    Upserted whenever a route completes (or is re-selected). zone_id is
    NULL until Phase 4 delivers zone attribution.
    """

    __tablename__ = "analytics_route_metrics_snapshot"

    __table_args__ = (
        Index("ix_analytics_rms_team_created", "team_id", "created_at"),
        Index("ix_analytics_rms_expected_start", "expected_start_time"),
        Index("ix_analytics_rms_zone_id", "zone_id"),
        Index("ix_analytics_rms_zone_version_id", "zone_version_id"),
        Index("ix_analytics_rms_team_zone_version_zone", "team_id", "zone_version_id", "zone_id"),
    )

    id = Column(Integer, primary_key=True)
    route_solution_id = Column(
        Integer,
        ForeignKey("route_solution.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    team_id = Column(Integer, nullable=False, index=True)

    expected_start_time = Column(UTCDateTime, nullable=True)
    computed_at = Column(UTCDateTime, nullable=False)

    # Stop-level delay metrics
    total_stops = Column(Integer, nullable=False, default=0)
    on_time_stops = Column(Integer, nullable=False, default=0)
    early_stops = Column(Integer, nullable=False, default=0)
    late_stops = Column(Integer, nullable=False, default=0)
    avg_delay_seconds = Column(Float, nullable=False, default=0.0)
    max_delay_seconds = Column(Float, nullable=False, default=0.0)
    on_time_rate = Column(Float, nullable=False, default=0.0)
    delay_rate = Column(Float, nullable=False, default=0.0)

    # Route efficiency metrics
    total_distance_meters = Column(Float, nullable=False, default=0.0)
    total_travel_time_seconds = Column(Float, nullable=False, default=0.0)
    total_service_time_seconds = Column(Float, nullable=False, default=0.0)
    total_orders = Column(Integer, nullable=False, default=0)

    # Spatial dimension (NULL until Phase 4)
    zone_id = Column(Integer, nullable=True)
    zone_version_id = Column(Integer, nullable=True)

    created_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
