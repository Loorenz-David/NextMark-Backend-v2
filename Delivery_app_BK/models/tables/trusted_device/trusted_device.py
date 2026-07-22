from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class TrustedDevice(db.Model, TeamScopedMixin):
    __tablename__ = "trusted_device"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False)
    device_secret_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(UTCDateTime, nullable=True)
    created_at = Column(
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
    registered_by_user_id = Column(
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

    assignments = relationship(
        "TrustedDeviceUser",
        back_populates="trusted_device",
        lazy="selectin",
    )
