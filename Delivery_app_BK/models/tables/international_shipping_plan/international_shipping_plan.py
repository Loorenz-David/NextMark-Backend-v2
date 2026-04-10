# Third-party dependecies
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class InternationalShippingPlan(db.Model, TeamScopedMixin):
    __tablename__ = "international_shipping_plan"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    carrier_name = Column(String)

    route_plan_id = Column(
        Integer,
        ForeignKey("route_plan.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    route_plan = relationship("RoutePlan")