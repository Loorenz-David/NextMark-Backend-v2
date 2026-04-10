from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text

from Delivery_app_BK.models.utils import UTCDateTime


class DispatchStateMixin:
    DISPATCH_STATUS_PENDING = "PENDING"
    DISPATCH_STATUS_CLAIMED = "CLAIMED"
    DISPATCH_STATUS_DISPATCHED = "DISPATCHED"
    DISPATCH_STATUS_FAILED = "FAILED"
    DISPATCH_STATUS_DEAD = "DEAD"

    event_id = Column(String, nullable=True, unique=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True, index=True)
    entity_version = Column(String, nullable=True, index=True)
    dispatch_status = Column(String, nullable=False, index=True, default=DISPATCH_STATUS_PENDING)
    dispatch_attempts = Column(Integer, nullable=False, default=0)
    claimed_at = Column(UTCDateTime, nullable=True, index=True)
    claimed_by = Column(String, nullable=True, index=True)
    next_attempt_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    last_error = Column(Text, nullable=True)
    relayed_at = Column(UTCDateTime, nullable=True, index=True)
