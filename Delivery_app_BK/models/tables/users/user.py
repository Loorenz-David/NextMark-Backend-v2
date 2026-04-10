# Thirs-party dependencies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON
from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.models.mixins.validation_mixins.phone_number_validation import (
    PhoneNumberJSONValidationMixin
)
from Delivery_app_BK.models.mixins.validation_mixins.address_validation import (
    AddressJSONValidationMixin
)

from werkzeug.security import generate_password_hash, check_password_hash 


class User(
    db.Model,
    TeamScopedMixin,
    PhoneNumberJSONValidationMixin,
    AddressJSONValidationMixin
):
    __tablename__ = "user"

    
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    username = Column(String, unique= True, nullable=False, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password = Column(String, nullable=False)
    phone_number = Column(JSONB().with_variant(JSON, "sqlite"))
    
    
    profile_picture = Column(JSONB().with_variant(JSON, "sqlite"))

    primals_team_id = Column(Integer, nullable=True)
    primals_role_id = Column(Integer, nullable=True)
    team_workspace_team_id = Column(Integer, nullable=True)
    team_workspace_role_id = Column(Integer, nullable=True)
    admin_app_current_workspace = Column(String, nullable=True)
    driver_app_current_workspace = Column(String, nullable=True)
    
    show_app_tutorial = Column(Boolean, default=True)

    last_online = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))
    last_location = Column(JSONB().with_variant(JSON, "sqlite"))  


    user_role_id = Column(
        Integer, 
        ForeignKey("user_role.id")
    )

   
    
    team = relationship(
        "Team",
        backref="members",
        lazy="selectin"
    )


    user_role = relationship(
        "UserRole",
        back_populates="users",
        lazy="selectin"
    )

   

    case_chats = relationship(
        "CaseChat",
        back_populates="user",
        lazy="selectin",
    )

    route_solutions = relationship(
        "RouteSolution",
        back_populates = "driver"
    )

    store_pickup_plans = relationship(
        "StorePickupPlan",
        back_populates = "assigned_user"
    )

    shopify_integrations = relationship(
        "ShopifyIntegration",
        back_populates="user",
        lazy="selectin"
    )


    

    def hash_password(self, password):
        return generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
