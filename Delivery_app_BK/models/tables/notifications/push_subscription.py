from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class PushSubscription(db.Model):
    __tablename__ = "push_subscription"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    expiration_time = Column(Text, nullable=True)
    subscription_json = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(UTCDateTime, nullable=True)
    created_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User")
