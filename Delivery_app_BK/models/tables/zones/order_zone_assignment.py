from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Enum, Index, Integer, String, UniqueConstraint

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class OrderZoneAssignment(db.Model):
    """Current persisted zone assignment for an order."""

    __tablename__ = "order_zone_assignment"

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_order_zone_assignment_order_id"),
        Index("ix_order_zone_assignment_scope", "team_id", "city_key", "zone_version_id"),
        Index("ix_order_zone_assignment_unassigned", "team_id", "is_unassigned", "assigned_at"),
    )

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, db.ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(Integer, db.ForeignKey("zone.id", ondelete="SET NULL"), nullable=True, index=True)
    zone_version_id = Column(
        Integer,
        db.ForeignKey("zone_version.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    city_key = Column(String(255), nullable=False, index=True)
    assignment_type = Column(
        Enum("auto", "manual", name="zone_assignment_type_enum"),
        nullable=False,
        default="auto",
    )
    assignment_method = Column(
        Enum(
            "polygon_direct",
            "centroid_fallback",
            "bootstrap_fallback",
            "manual_override",
            name="zone_assignment_method_enum",
        ),
        nullable=True,
    )
    is_unassigned = Column(Boolean, nullable=False, default=False)
    unassigned_reason = Column(
        Enum(
            "no_coordinates",
            "no_candidate_zone",
            "polygon_miss",
            "below_threshold",
            name="zone_unassigned_reason_enum",
        ),
        nullable=True,
    )
    assigned_at = Column(
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
