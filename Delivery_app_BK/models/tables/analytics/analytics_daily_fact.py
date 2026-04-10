"""ORM model for per-team daily analytics aggregates."""
from datetime import datetime, timezone

from sqlalchemy import Column, Date, Float, Index, Integer
from sqlalchemy import text

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class AnalyticsDailyFact(db.Model):
    """One row per (team, date) [or (team, date, zone) once Phase 4 lands].

    Unique constraint is implemented via two partial unique indexes because
    PostgreSQL treats NULL != NULL in standard UniqueConstraint:
      - global row:  zone_id IS NULL  → index over (team_id, date)
      - zoned  row:  zone_id IS NOT NULL → index over (team_id, date, zone_id)
    """

    __tablename__ = "analytics_daily_fact"

    __table_args__ = (
        # Unique: one global row per (team, date)
        Index(
            "uix_analytics_daily_global",
            "team_id",
            "date",
            unique=True,
            postgresql_where=text("zone_id IS NULL"),
        ),
        # Unique: one zoned row per (team, date, zone)
        Index(
            "uix_analytics_daily_zoned",
            "team_id",
            "date",
            "zone_version_id",
            "zone_id",
            unique=True,
            postgresql_where=text("zone_id IS NOT NULL"),
        ),
        # Query index
        Index(
            "ix_analytics_daily_fact_team_date_zone",
            "team_id",
            "date",
            "zone_version_id",
            "zone_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False)

    # Order-level aggregates
    total_orders_created = Column(Integer, nullable=False, default=0)
    total_orders_completed = Column(Integer, nullable=False, default=0)
    total_orders_failed = Column(Integer, nullable=False, default=0)
    scheduled_orders = Column(Integer, nullable=False, default=0)
    unscheduled_orders = Column(Integer, nullable=False, default=0)
    completion_rate = Column(Float, nullable=False, default=0.0)

    # Route-level aggregates
    total_routes = Column(Integer, nullable=False, default=0)
    routes_completed = Column(Integer, nullable=False, default=0)
    routes_active = Column(Integer, nullable=False, default=0)
    avg_delay_seconds = Column(Float, nullable=False, default=0.0)
    late_routes_count = Column(Integer, nullable=False, default=0)
    on_time_routes_count = Column(Integer, nullable=False, default=0)
    total_distance_meters = Column(Float, nullable=False, default=0.0)
    total_travel_time_seconds = Column(Float, nullable=False, default=0.0)

    # Spatial — None = global aggregate row
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
