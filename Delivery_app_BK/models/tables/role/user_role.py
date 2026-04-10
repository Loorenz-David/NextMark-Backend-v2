# Thirs-party dependencies
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey

# Local application imports
from Delivery_app_BK.models import db

from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin

"""
the static roles are:

- Admin: 
- Assistant:
- Driver:

"""

class UserRole(db.Model, TeamScopedMixin):
    __tablename__ = "user_role"
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    role_name = Column(String, nullable=False, index=True)
    description = Column(String)

    is_system = Column(Boolean, default=False, index=True)


    base_role_id = Column(
        Integer,
        ForeignKey("base_role.id")
    )

    users = relationship(
        "User",
        back_populates = "user_role",
        lazy = 'selectin'
    )


    base_role = relationship(
        "BaseRole",
        back_populates = "user_roles",
        lazy = 'selectin'
    )

    date_range_access_rule = relationship(
        "DateRangeAccessRule",
        back_populates = "user_role"
    )

    order_state_transition_rule = relationship(
        "OrderStateTransitionRule",
        back_populates = "user_role"
    )

    
