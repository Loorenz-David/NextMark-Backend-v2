from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship, validates

# Local application imports
from Delivery_app_BK.errors.validation import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanState as PlanStateEnum

"""
current static states are:
- Scheduled 
- In Progress
- Completed

"""


class RoutePlanState(db.Model, TeamScopedMixin):
    __tablename__ = "plan_state"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, index=True)
    index = Column(Integer)
    color = Column(String)

    is_system = Column(Boolean, default=False, index=True)

    route_plans = relationship("RoutePlan", back_populates="state")
    route_groups = relationship("RouteGroup", back_populates="state")

    team = relationship(
        "Team",
        backref="plan_states",
        lazy=True,
    )

    @validates("name")
    def validate_name(self, key, value):
        if not value:
            raise ValidationFailed("RouteState name cannot be empty.")
        if value not in PlanStateEnum._value2member_map_:
            raise ValidationFailed(
                f"Invalid RouteState name '{value}'. "
                f"Allowed values: {[e.value for e in PlanStateEnum]}"
            )
        return value
