# Third-party dependecies

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer,  ForeignKey, String, Boolean, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone

# Local application imports

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.mixins.validation_mixins.service_time_validation import (
    ServiceTimeJSONValidationMixin,
)
from Delivery_app_BK.models.utils import UTCDateTime



class RouteSolutionStop(db.Model, TeamScopedMixin, ServiceTimeJSONValidationMixin):
    __tablename__ = "route_solution_stop"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    route_solution_id = Column(
        Integer,
        ForeignKey("route_solution.id", ondelete="CASCADE"),
        nullable=False
    )

    order_id = Column(
        Integer, 
        ForeignKey("order.id", ondelete="CASCADE")
    )

    # legacy free-form duration kept for backwards compatibility
    service_duration = Column(String) # sec
    service_time = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    
    

    in_range = Column(Boolean)
    # the order placement when being deliver
    stop_order = Column(Integer, nullable=True)
    reason_was_skipped = Column(String)

    has_constraint_violation = Column(Boolean, default=False)
    constraint_warnings = Column(JSONB, nullable=True)

    eta_status = Column(
        Enum("valid", "estimated", "stale", name="eta_status"),
        nullable=False,
        default="stale"
    )
    
    expected_arrival_time = Column(UTCDateTime)
    expected_service_duration_seconds = Column(Integer)
    # expected_departure_time is derived from:
    # expected_arrival_time + expected_service_duration_seconds
    # It represents when the vehicle leaves the stop after service.
    expected_departure_time = Column(UTCDateTime)
    actual_arrival_time = Column(UTCDateTime)
    # Future: used to compute service duration
    # service_duration_seconds = actual_departure_time - actual_arrival_time
    actual_departure_time = Column(UTCDateTime)
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    to_next_polyline = Column(JSONB, nullable=True)

    route_solution = relationship(
        "RouteSolution",
        back_populates="stops",

    )
