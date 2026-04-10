# Third-party dependencies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy import Column, Integer, String, Boolean, JSON

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.mixins.validation_mixins.address_validation import (
    AddressJSONValidationMixin,
)
from Delivery_app_BK.services.domain.facility import (
    validate_facility_type,
    validate_operating_hours,
)


class Facility(db.Model, TeamScopedMixin, AddressJSONValidationMixin):
    __tablename__ = "facility"

    __address_fields__ = ("location",)

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)

    property_location = Column(JSONB().with_variant(JSON, "sqlite"))
    # dict: {city, street_address, postal_code, building_floor, coordinates}

    # Type discriminator — enables conditional routing logic and AI reasoning
    # Values: "warehouse" | "depot" | "hub" | "pickup_point"
    facility_type = Column(
        String,
        nullable=False,
        default="warehouse",
        index=True,
    )

    # Dispatch capability — the single flag the optimizer queries when selecting a route start
    can_dispatch = Column(Boolean, nullable=False, default=False)

    # Return capability — whether this facility can receive returned orders
    can_receive_returns = Column(Boolean, nullable=False, default=False)

    # Operating hours — when the facility is open
    # Schema: [{"day": "mon", "open": "08:00", "close": "18:00"}, ...]
    # Days: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
    operating_hours = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    # Service time defaults — used when no vehicle-specific override is set
    default_loading_time_seconds = Column(Integer, nullable=False, default=600)
    default_unloading_time_seconds = Column(Integer, nullable=False, default=300)

    # Throughput cap — soft limit for optimizer and AI scheduling
    max_orders_per_day = Column(Integer, nullable=True)

    # External system references — for ERP, WMS, or third-party integrations
    # Schema: {"erp_id": "...", "wms_location_code": "...", "shopify_location_id": "..."}
    external_refs = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    team = relationship(
        "Team",
        backref="facilities",
        lazy=True,
    )

    @validates("facility_type")
    def validate_facility_type_field(self, key, value):
        return validate_facility_type(value)

    @validates("operating_hours")
    def validate_operating_hours_field(self, key, value):
        return validate_operating_hours(value)
