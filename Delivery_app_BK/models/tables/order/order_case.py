# Third-party dependecies
from marshmallow import validates
from sqlalchemy.orm import relationship
from sqlalchemy import Column,Text, Integer, String, ForeignKey

from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db

from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState as OrderCaseStateEnum
from Delivery_app_BK.errors.validation import ValidationFailed

class OrderCase(db.Model):
    __tablename__ = "order_case"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    state = Column(String, nullable=False)
    label = Column(String)
    creation_date = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order_id = Column(
        Integer,
        ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


    created_by = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    chats = relationship(
        "CaseChat",
        back_populates="order_case",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    order = relationship(
        "Order",
        back_populates="order_cases",
        lazy="selectin",
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="selectin",
    )

    @validates('state')
    def validate_state(self, key, value):
        if not value:
            raise ValidationFailed("OrderCaseState name cannot be empty.")
        if value not in OrderCaseStateEnum._value2member_map_:
            raise ValidationFailed(
                f"Invalid OrderCaseState name '{value}'. "
                f"Allowed values: {[e.value for e in OrderCaseStateEnum]}"
            )

        return value




class CaseChat(db.Model, TeamScopedMixin):
    __tablename__ = "case_chat"
    # change name to case_chat

    id = Column( Integer, primary_key = True )
    client_id = Column(String, index=True)
    message = Column( Text )
    user_name = Column(String, nullable=True)
    creation_date = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))



    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable= True
    )

    order_case_id = Column(
        Integer,
        ForeignKey("order_case.id", ondelete="CASCADE"),
        nullable= False
    )

    notification_reads = relationship(
        "NotificationRead",
        back_populates = "case_chat",
        cascade="all, delete-orphan"
    )

    user = relationship(
        "User",
        back_populates = "case_chats",
    )

    order_case = relationship(
        "OrderCase",
        back_populates = "chats",
    )
