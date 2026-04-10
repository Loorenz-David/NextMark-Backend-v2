# Third-party dependecies
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates

# Local application import

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.services.domain.order.order_states import OrderState as OrderStateEnum





class RouteGroup(db.Model, TeamScopedMixin):
    __tablename__ = "route_group"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    route_plan_id = Column(
        Integer,
        ForeignKey("route_plan.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    zone_id = Column(Integer, ForeignKey("zone.id", ondelete="SET NULL"), nullable=True, index=True)
    is_system_default_bucket = Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("false"),
        index=True,
    )
    zone_geometry_snapshot = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    template_snapshot = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    state_id = Column(Integer, ForeignKey("plan_state.id", ondelete="SET NULL"))

    total_weight_g = Column(Float, nullable=True)
    total_volume_cm3 = Column(Float, nullable=True)
    total_item_count = Column(Integer, nullable=True)
    total_orders = Column(Integer, nullable=True)
    order_state_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    item_type_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    

    route_solutions = relationship(
        "RouteSolution",
        back_populates="route_group",
        cascade="all, delete-orphan",
    )

    route_plan = relationship(
        "RoutePlan",
        back_populates="route_groups",
    )

    zone = relationship("Zone", lazy="selectin")

    state = relationship(
        "RoutePlanState",
        back_populates="route_groups",
        lazy="selectin",
    )

    team = relationship(
        "Team",
        backref="route_groups",
        lazy=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "route_plan_id",
            "zone_id",
            name="uq_route_group_team_plan_zone",
        ),
    )

    @validates("order_state_counts")
    def validate_order_state_counts(self, key, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("order_state_counts must be a dict.")
        valid_states = {state.value for state in OrderStateEnum}
        invalid = [state_name for state_name in value if state_name not in valid_states]
        if invalid:
            raise ValueError(
                f"order_state_counts keys must be valid OrderState values. Invalid: {invalid}"
            )
        return value
