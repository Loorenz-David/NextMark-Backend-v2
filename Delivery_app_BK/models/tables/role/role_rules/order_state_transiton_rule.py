# Thirs-party dependencies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, JSON

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class OrderStateTransitionRule(db.Model, TeamScopedMixin):
    __tablename__ = "order_state_transition_rule"
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    
    allowed_state_id = Column(
        Integer,
        ForeignKey("order_state.id")
    )
    
    user_role_id = Column(
        Integer,
        ForeignKey("user_role.id"),
    )

    user_role = relationship(
        "UserRole",
        back_populates = "order_state_transition_rule"
    )
    
    allowed_state = relationship(
        "OrderState",
        back_populates = "order_state_transition_rules"
    )

    team = relationship(
        "Team",
        backref="order_state_transition_rules",
        lazy=True
    )
