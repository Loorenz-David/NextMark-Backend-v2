# Third-party dependecies

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float

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


# model definition of an order
class Order(
    db.Model,
    TeamScopedMixin,
    PhoneNumberJSONValidationMixin,
    AddressJSONValidationMixin
):
    __tablename__ = "order"

 
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    """
    must create a schema validator for the order_plan_objectives:
    the allowed values are the plan types table names. 
    """
    order_plan_objective= Column(String, index=True)

    order_scalar_id = Column(Integer, index=True)
    reference_number = Column( String, index= True )
    external_order_id = Column( String, index = True )
    external_source = Column( String, index = True )
    # External tracking supplied by Shopify / third-party couriers (writable).
    external_tracking_number = Column( String, index = True )
    external_tracking_link = Column( String, index = True )

    # System-managed immutable tracking fields (auto-generated on creation).
    tracking_number = Column( String, index = True )
    tracking_link = Column( String, index = True )

    # Public order-tracking secure-token fields
    tracking_token_hash = Column(String(64), unique=True, nullable=True, index=True)
    tracking_token_created_at = Column(UTCDateTime, nullable=True)

    client_first_name = Column(String, index=True)
    client_last_name = Column(String, index=True)
    client_email = Column(String, index=True)
    client_primary_phone = Column(JSONB().with_variant(JSON, "sqlite"))  
    client_secondary_phone = Column(JSONB().with_variant(JSON, "sqlite"))  
    client_address = Column(JSONB().with_variant(JSON, "sqlite"))  

    operation_type = Column(String, index=True, default="dropoff")

    marketing_messages = Column(Boolean, default=False)

    creation_date = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    items_updated_at = Column(UTCDateTime)

    # Denormalized order totals — recomputed on every item mutation.
    total_weight_g = Column(Float, nullable=True)
    total_volume_cm3 = Column(Float, nullable=True)
    total_item_count = Column(Integer, nullable=True)

    order_state_id = Column(
        Integer,
        ForeignKey("order_state.id", ondelete="SET NULL")
    )
    
    delivery_plan_id = Column(
        Integer,
        ForeignKey("route_plan.id", ondelete="SET NULL"),
    )
    costumer_id = Column(
        Integer,
        ForeignKey("costumer.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    archive_at = Column(UTCDateTime)

    # Client-form secure link fields
    client_form_token_hash = Column(String(64), unique=True, nullable=True, index=True)
    client_form_token_expires_at = Column(UTCDateTime, nullable=True)
    client_form_submitted_at = Column(UTCDateTime, nullable=True)

    # Order notes: list of string notes attached to the order
    order_notes = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

  

    # delivery_items has change to items, there is a lot of the fornt end that needs to be updated!
    items = db.relationship(
        "Item",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    state = relationship(
        "OrderState",
        back_populates="order",
        lazy="selectin"
    )

    state_history = relationship(
        "OrderStateHistory",
        back_populates="order",
        lazy="selectin"
    )

    events = relationship(
        "OrderEvent",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    order_cases = relationship(
        "OrderCase",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    route_plan = relationship(
        "RoutePlan",
        back_populates="orders",
        foreign_keys=[delivery_plan_id],
    )

    costumer = relationship(
        "Costumer",
        back_populates="orders",
        lazy="selectin",
    )

    delivery_windows = relationship(
        "OrderDeliveryWindow",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    team = relationship(
        "Team",
        backref="orders",
    )

    __table_args__ = (
        UniqueConstraint("team_id", "order_scalar_id", name="uq_order_team_scalar_id"),
        Index("ix_order_creation_date_id_desc", creation_date.desc(), id.desc()),
        # JSONB GIN indexes
        Index("ix_order_client_primary_phone_gin", client_primary_phone, postgresql_using="gin"),
        Index("ix_order_client_secondary_phone_gin", client_secondary_phone, postgresql_using="gin"),
        Index("ix_order_client_address_gin", client_address, postgresql_using="gin"),

        # Full-text index for partial string search
        Index(
            "ix_order_client_address_tsvector",
            text("to_tsvector('simple', client_address::text)"),
            postgresql_using="gin"
        ),
    )


    ORDER_PLAN_INTENTIONS = {
        "local_delivery",
        "international_shipping",
        "store_pickup",
    }

    ORDER_OPERATION_TYPE = {
        "pickup",
        "dropoff",
        "pickup_dropoff",
    }

    @validates("order_plan_objective")
    def validate_order_plan_intention(self, key, value):
        if value is None:
            return value  # allow unset orders

        if value not in self.ORDER_PLAN_INTENTIONS:
            raise ValueError(
                f"Invalid order_plan_objective '{value}'. "
                f"Allowed values: {self.ORDER_PLAN_INTENTIONS}"
            )
        return value
    
    @validates("operation_type")
    def validate_order_operation_type(self, key, value):
        if value is None:
            return value
        if value not in self.ORDER_OPERATION_TYPE:
            raise ValueError(
                f"Invalid order operation_type: {value}. "
                f"Allowed values: {self.ORDER_OPERATION_TYPE}"
            )
        return value
