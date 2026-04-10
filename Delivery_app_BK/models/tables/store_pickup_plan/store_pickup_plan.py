# Third-party dependecies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.validation_mixins.address_validation import AddressJSONValidationMixin

from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class StorePickupPlan(
    db.Model,
    TeamScopedMixin,
    AddressJSONValidationMixin,
):
    __tablename__ = "store_pickup_plan"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    pickup_location = Column(JSONB().with_variant(JSON, "sqlite"))

    assigned_user_id = Column(
        Integer,
        ForeignKey("user.id")
    )

    route_plan_id = Column(
        Integer,
        ForeignKey("route_plan.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    assigned_user = relationship(
        "User",
        back_populates="store_pickup_plans",
    )

    route_plan = relationship("RoutePlan")