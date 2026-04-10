from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey

from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime

class OrderStateHistory(db.Model, TeamScopedMixin):
    __tablename__ = "order_state_history"

    id = Column( Integer, primary_key=True )
    client_id = Column(String, index=True)

    changed_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), index=True)

    source = Column(String)

    from_state_id = Column(
        Integer,
        ForeignKey("order_state.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_state_id = Column(
        Integer,
        ForeignKey("order_state.id", ondelete="SET NULL"),
        nullable=True,
    )

    changed_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    from_state = relationship(
        "OrderState",
        foreign_keys=[from_state_id],
    )
    to_state = relationship(
        "OrderState",
        foreign_keys=[to_state_id],
    )
    order = relationship(
        "Order",
        back_populates="state_history",
    )
    changed_by_user = relationship(
        "User",
    )
