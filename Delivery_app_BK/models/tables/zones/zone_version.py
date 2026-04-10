from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Index, Integer, String, UniqueConstraint, text

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class ZoneVersion(db.Model):
    """Immutable zone version scoped to a team and normalized city key."""

    __tablename__ = "zone_version"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "city_key",
            "version_number",
            name="uq_zone_version_team_city_version",
        ),
        Index(
            "uix_zone_version_active_team_city",
            "team_id",
            "city_key",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
        Index("ix_zone_version_team_city_created", "team_id", "city_key", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, db.ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)
    city_key = Column(String(255), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
