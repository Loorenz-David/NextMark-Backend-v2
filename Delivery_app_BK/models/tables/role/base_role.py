# Thirs-party dependencies
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean

# Local application imports
from Delivery_app_BK.models import db

from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin

"""
the static roles are:

- ADMIN: 
- ASSISTANT:
- DRIVER:

"""

class BaseRole(db.Model, TeamScopedMixin):
    __tablename__ = "base_role"
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    role_name = Column(String, nullable=False, index=True)
    description = Column(String)


    is_system = Column(Boolean, default=False, index=True)



    user_roles = relationship(
        "UserRole",
        back_populates="base_role",
    )