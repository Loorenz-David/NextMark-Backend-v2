# Third-party dependencies
from sqlalchemy.orm import relationship, validates
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.services.domain.vehicle import (
    validate_fuel_type,
    validate_travel_mode,
    validate_vehicle_capabilities,
    validate_vehicle_status,
)

"""

Vehicle (v1 → v2 evolution – implementation oriented)

This table represents a mobile operational resource in the logistics system.

A vehicle is NOT just a transport unit. It is a constraint carrier and cost unit
within the routing and optimization engine.

---

V1 Scope (current responsibilities):
- Identity (registration_number, label)
- Physical constraints (volume, weight, speed)
- Cost model (cost_per_km, cost_per_hour)
- Travel limits (distance, duration)
- Basic classification (fuel_type, travel_mode)

This supports:
- Basic route planning
- Cost estimation
- Simple constraint validation

---

Domain Direction (core concept):

A vehicle is a dynamic resource that:
- Executes routes
- Consumes capacity
- Adds cost to the system
- Constrains feasibility of delivery plans

Vehicles interact with:
- Facilities (start/end locations)
- Orders (capacity + compatibility)
- Routes (execution layer)
- AI operator (decision making)

---

V2 Implementation (recommended next step)

Below are the extensions that SHOULD be implemented incrementally.

---

1. Facility Assignment (CRITICAL)

Intent:
Define where the vehicle operates from.

Usability:
- Enables multi-depot routing
- Defines route start/end points
- Allows AI to assign vehicles correctly

Implementation:
    start_facility_id = Column(Integer, ForeignKey("facility.id"))
    end_facility_id = Column(Integer, ForeignKey("facility.id"), nullable=True)

---

2. Driver Association

Intent:
Link vehicle to a driver/operator.

Usability:
- Scheduling and accountability
- AI reasoning about availability

Implementation:
    driver_id = Column(Integer, ForeignKey("user.id"), nullable=True)

---

3. Availability & Scheduling (VERY IMPORTANT)

Intent:
Define when the vehicle can operate.

Usability:
- Route feasibility validation
- Prevent invalid planning

Implementation:
    availability_schedule = Column(JSONB)
    # [{day: "mon", start: "08:00", end: "17:00"}]

    is_active = Column(Boolean, default=True)

---

4. Capabilities (AI + routing intelligence)

Intent:
Define what the vehicle can handle.

Usability:
- Match orders with compatible vehicles
- AI decision making

Implementation:
    capabilities = Column(JSONB)
    # ["fragile", "cold_chain", "heavy_load", "returns"]

---

5. Loading / Service Behavior

Intent:
Model time impact per stop.

Usability:
- Improves ETA accuracy
- Better optimization results

Implementation:
    loading_time_per_stop_seconds = Column(Integer, default=0)
    unloading_time_per_stop_seconds = Column(Integer, default=0)

---

6. Operational State

Intent:
Track real-time or logical state of the vehicle.

Usability:
- UI representation
- AI reasoning
- Operational control

Implementation:
    status = Column(String, default="idle")
    # idle | in_route | loading | offline | maintenance

---

7. Reliability / Maintenance

Intent:
Control whether a vehicle can be used.

Usability:
- Avoid assigning unavailable vehicles
- Maintenance tracking

Implementation:
    is_available_for_routing = Column(Boolean, default=True)
    last_maintenance_at = Column(DateTime)

---

8. Real-time Position (future extension)

Intent:
Track vehicle location dynamically.

Usability:
- Live tracking
- Dynamic re-routing
- AI monitoring

Implementation:
    current_location = Column(JSONB)
    # {lat, lng}

---

9. Optimization Enhancements

Intent:
Improve solver decision-making.

Usability:
- Better cost-aware routing
- Smarter vehicle selection

Implementation:
    priority_score = Column(Integer, default=0)
    fixed_cost = Column(Float, default=0)

---

Important Notes:
- Implement incrementally, not all at once
- Prioritize: facility assignment → availability → capabilities
- This entity is a core resource in the routing engine
- Vehicles should be treated as constrained resources, not static data
- Future evolution may include tighter integration with route execution tracking



"""

class Vehicle(db.Model, TeamScopedMixin):
    __tablename__ = "vehicle"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    registration_number = Column(String, nullable=False, index=True)
    label = Column(String, nullable=True)

    fuel_type = Column(String, nullable=True)
    travel_mode = Column(String, nullable=True)

    max_volume_load_cm3 = Column(Integer, nullable=True)
    max_weight_load_g = Column(Integer, nullable=True)
    max_speed_kmh = Column(Float, nullable=True)

    cost_per_km = Column(Float, default=0)
    cost_per_hour = Column(Float, default=0)

    travel_distance_limit_km = Column(Integer, nullable=True)
    travel_duration_limit_minutes = Column(Integer, nullable=True)

    is_system = Column(Boolean, default=False, index=True)

    # Home facility — where this vehicle is based
    home_facility_id = Column(
        Integer,
        ForeignKey("facility.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Operational state — current state of the vehicle for UI and AI reasoning
    # Values: "idle" | "in_route" | "loading" | "offline" | "maintenance"
    status = Column(String, nullable=False, default="idle", index=True)

    # Availability flag — hard off-switch; overrides scheduling
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Capabilities — what this vehicle can carry; matched against order requirements
    # Schema: ["cold_chain", "fragile", "heavy_load", "returns", "oversized"]
    capabilities = Column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    # Per-stop service time — improves ETA accuracy
    loading_time_per_stop_seconds = Column(Integer, nullable=False, default=0)
    unloading_time_per_stop_seconds = Column(Integer, nullable=False, default=0)

    # Fixed routing cost — used by cost-aware optimizer scoring
    fixed_cost = Column(Float, nullable=False, default=0.0)

    team = relationship(
        "Team",
        backref="vehicles",
        lazy=True,
    )

    home_facility = relationship(
        "Facility",
        foreign_keys=[home_facility_id],
        lazy="selectin",
    )

    @validates("fuel_type")
    def validate_fuel_type_field(self, key, value):
        return validate_fuel_type(value)

    @validates("travel_mode")
    def validate_travel_mode_field(self, key, value):
        return validate_travel_mode(value)

    @validates("status")
    def validate_status_field(self, key, value):
        return validate_vehicle_status(value)

    @validates("capabilities")
    def validate_capabilities_field(self, key, value):
        return validate_vehicle_capabilities(value)
