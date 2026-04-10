from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class ZoneTemplate(db.Model):
    """Reusable operational defaults attached to a zone definition."""

    __tablename__ = "zone_template"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("zone.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Facility anchor — the facility that dispatches orders for this zone
    default_facility_id = Column(
        Integer,
        ForeignKey("facility.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Route sizing — maximum orders per route solution in this zone
    max_orders_per_route = Column(Integer, nullable=True)

    # Vehicle count cap — how many route solutions to create for this zone's route group
    max_vehicles = Column(Integer, nullable=True)

    # Operating window — applied to route solutions created from this template
    operating_window_start = Column(String(5), nullable=True)   # "HH:MM"
    operating_window_end = Column(String(5), nullable=True)     # "HH:MM"

    # ETA tolerance — default stamped onto route solutions
    eta_tolerance_seconds = Column(Integer, nullable=False, default=0)

    # Capability filter — only vehicles with ALL of these capabilities are eligible
    # Schema: ["cold_chain", "fragile"]
    vehicle_capabilities_required = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    # Preferred vehicles — soft preference list used by AI before selecting from pool
    # Schema: [1, 4, 7]  (vehicle.id values scoped to this team)
    preferred_vehicle_ids = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    # Route end strategy default — stamped onto route solutions at creation
    # Values: "round_trip" | "custom_end_address" | "end_at_last_stop"
    default_route_end_strategy = Column(
        String,
        nullable=False,
        default="round_trip",
    )

    # Meta — escape hatch for unstructured or future config
    meta = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    zone = relationship("Zone", back_populates="templates")

    default_facility = relationship(
        "Facility",
        foreign_keys=[default_facility_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "uq_zone_template_active_per_zone",
            "team_id",
            "zone_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )
