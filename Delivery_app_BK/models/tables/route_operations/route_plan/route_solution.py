# Third-party dependecies

from sqlalchemy.orm import relationship, validates
from sqlalchemy import Column, Integer,  ForeignKey, String, Float, Boolean, JSON, Enum
from sqlalchemy.dialects.postgresql import JSONB

from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models.mixins.validation_mixins.address_validation import AddressJSONValidationMixin
from Delivery_app_BK.models.mixins.validation_mixins.service_time_validation import (
    ServiceTimeJSONValidationMixin,
)

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
    IS_OPTIMIZED_VALUES,
)
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP, CUSTOM_END_ADDRESS,LAST_STOP
from Delivery_app_BK.services.domain.route_operations.route_solution import RouteActualEndTimeSource



class RouteSolution(
    db.Model,
    TeamScopedMixin,
    AddressJSONValidationMixin,
    ServiceTimeJSONValidationMixin,
):
    __tablename__ = "route_solution"


    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    label = Column(String)
    version = Column(Integer, default=1)
    algorithm = Column(String)
    score = Column(Float)  # distance, time, cost score, etc.

    total_distance_meters = Column(Integer)
    total_travel_time_seconds = Column(Integer)
    


    # expected times are what the optimization fill in 
    expected_start_time = Column(UTCDateTime)
    expected_end_time = Column(UTCDateTime)
    actual_start_time = Column(UTCDateTime)
    actual_end_time = Column(UTCDateTime)
    actual_end_time_source = Column(String, nullable=True)

    has_route_warnings = Column(Boolean, default=False)
    route_warnings = Column(JSONB, nullable=True)

    start_location = Column(JSONB().with_variant(JSON, "sqlite"))
    end_location = Column(JSONB().with_variant(JSON, "sqlite"))
    
    route_end_strategy = Column(
        Enum(
            ROUND_TRIP,
            CUSTOM_END_ADDRESS,
            LAST_STOP,
            name="route_end_strategy"
        ),
        nullable=False,
        default=ROUND_TRIP
    )
    
    # set times are what the user inputed
    # maybe this should be string times also...
    # and they infer a repeated allowed time accross the delivery plan date range
    set_start_time = Column( String )
    set_end_time = Column( String )
    # Arrival tolerance around expected arrival time, in seconds.
    eta_tolerance_seconds = Column(Integer, nullable=False, default=0)
    eta_message_tolerance = Column(Integer, nullable=True, default=1800)
    stops_service_time = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    created_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    is_selected = Column(Boolean, default=False)

    """
    must add a schema validator for is_optimize values:
    "optimize","partial optimize", "not optimize"
    """
    is_optimized = Column(
                            Enum(*IS_OPTIMIZED_VALUES, name="is_optimized"),
                            nullable=False,
                            default=IS_OPTIMIZED_NOT_OPTIMIZED
    )

    driver_id = Column(
        Integer, 
        ForeignKey("user.id")
    )

    vehicle_id = Column(
        Integer,
        ForeignKey("vehicle.id"),
        nullable=True,
    )

    route_group_id = Column(
        Integer,
        ForeignKey("route_group.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_leg_polyline = Column(JSONB, nullable=True)
    end_leg_polyline = Column(JSONB, nullable=True)

    start_facility_id = Column(
        Integer,
        ForeignKey("facility.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    end_facility_id = Column(
        Integer,
        ForeignKey("facility.id", ondelete="SET NULL"),
        nullable=True,
    )

    stops = relationship(
        "RouteSolutionStop",
        back_populates = "route_solution",
        cascade = 'all, delete-orphan',
        order_by="RouteSolutionStop.stop_order"
    )


    driver = relationship(
        "User",
        back_populates="route_solutions",
    )

    vehicle = relationship(
        "Vehicle",
        lazy="selectin",
    )

    start_facility = relationship(
        "Facility",
        foreign_keys=[start_facility_id],
        lazy="selectin",
    )

    end_facility = relationship(
        "Facility",
        foreign_keys=[end_facility_id],
        lazy="selectin",
    )

    route_group = relationship(
        "RouteGroup",
        back_populates="route_solutions",
    )

    @validates("eta_tolerance_seconds")
    def validate_eta_tolerance_seconds(self, key, value):
        if value is None:
            return 0
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("eta_tolerance_seconds must be an integer.")
        if value < 0 or value > 7200:
            raise ValueError("eta_tolerance_seconds must be between 0 and 7200.")
        return value

    @validates("eta_message_tolerance")
    def validate_eta_message_tolerance(self, key, value):
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("eta_message_tolerance must be an integer.")
        if value < 0 or value > 7200:
            raise ValueError("eta_message_tolerance must be between 0 and 7200.")
        return value

    @validates("actual_end_time_source")
    def validate_actual_end_time_source(self, key, value):
        if value is None:
            return None
        if isinstance(value, RouteActualEndTimeSource):
            return value.value
        if not isinstance(value, str):
            raise ValueError(
                f"actual_end_time_source must be one of {RouteActualEndTimeSource.values()}."
            )
        try:
            return RouteActualEndTimeSource(value).value
        except ValueError as error:
            raise ValueError(
                f"actual_end_time_source must be one of {RouteActualEndTimeSource.values()}."
            ) from error
