from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class TrustedDeviceEvent(db.Model, TeamScopedMixin):
    """Security-audit record for trusted-device operations.

    Never stores raw secrets, passwords, or tokens. ``detail`` carries only
    non-sensitive structured context (e.g. exclusion counts, error codes).
    """

    __tablename__ = "trusted_device_event"

    id = Column(Integer, primary_key=True)
    event_name = Column(String, nullable=False, index=True)
    result = Column(String, nullable=False)
    trusted_device_id = Column(
        Integer,
        ForeignKey("trusted_device.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    initiating_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    detail = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    created_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
