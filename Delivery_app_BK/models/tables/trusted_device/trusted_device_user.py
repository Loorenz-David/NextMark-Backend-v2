from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class TrustedDeviceUser(db.Model):
    __tablename__ = "trusted_device_user"
    __table_args__ = (
        UniqueConstraint(
            "trusted_device_id",
            "user_id",
            name="uq_trusted_device_user_device_user",
        ),
    )

    id = Column(Integer, primary_key=True)
    trusted_device_id = Column(
        Integer,
        ForeignKey("trusted_device.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at = Column(UTCDateTime, nullable=True)
    revoked_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    trusted_device = relationship(
        "TrustedDevice",
        back_populates="assignments",
    )
    user = relationship("User", foreign_keys=[user_id])
