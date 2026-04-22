from datetime import datetime, timezone

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class OrderEventAction(db.Model, TeamScopedMixin):
    __tablename__ = "order_event_action"

    STATUS_PENDING = "PENDING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"

    id = Column(Integer, primary_key=True)
    
    action_name = Column(String, nullable=False)
    action_scope = Column(String, nullable=False, default="", index=True)
    payload = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    status = Column(String, nullable=False, index=True, default=STATUS_PENDING)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    scheduled_for = Column(UTCDateTime, nullable=True, index=True)
    enqueued_at = Column(UTCDateTime, nullable=True, index=True)
    processed_at = Column(UTCDateTime, nullable=True, index=True)
    schedule_anchor_type = Column(String, nullable=True, index=True)
    schedule_anchor_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    event_id = Column(
        Integer,
        ForeignKey("order_event.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event = relationship("OrderEvent", back_populates="actions", lazy="selectin")
    team = relationship("Team", backref="order_event_actions", lazy=True)

    __table_args__ = (
        UniqueConstraint("event_id", "action_name", "action_scope", name="uq_order_event_action_event_scope"),
    )
